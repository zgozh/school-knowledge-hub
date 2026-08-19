"""人工数据入库：录入/上传/编辑/删除的业务编排（复用 ingest_document 管线）。"""
import uuid
from datetime import datetime

from collector.ingest.writer import ingest_document
from collector.lifecycle.validity import infer_expiry
from collector.parser.extract import ParsedArticle
from collector.tagger.rules import classify_category, rule_tag_topics
from shared.clients import get_milvus, get_minio, get_mongo
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("collector.manual")


async def create_document(payload: dict, mongo_db=None, milvus=None, minio=None, ingest_fn=None) -> str:
    doc_id = uuid.uuid4().hex[:16]
    url = payload.get("url") or f"manual://{doc_id}"
    await _ingest(doc_id, url, payload, mongo_db=mongo_db, milvus=milvus, minio=minio, ingest_fn=ingest_fn)
    return doc_id


async def update_document(doc_id: str, payload: dict, mongo_db=None, milvus=None, minio=None, ingest_fn=None) -> str | None:
    db = mongo_db or get_mongo()
    existing = await db["documents"].find_one({"doc_id": doc_id})
    if existing is None:
        return None
    url = payload.get("url") or existing.get("url") or f"manual://{doc_id}"
    merged = dict(payload)
    merged.setdefault("publish_date", existing.get("publish_date"))
    merged.setdefault("department", existing.get("department"))
    merged.setdefault("column", existing.get("column"))
    await _ingest(doc_id, url, merged, mongo_db=mongo_db, milvus=milvus, minio=minio, ingest_fn=ingest_fn)
    return doc_id


async def delete_document(doc_id: str, mongo_db=None, milvus=None, minio=None) -> bool:
    db = mongo_db or get_mongo()
    await db["documents"].delete_many({"doc_id": doc_id})
    (milvus or get_milvus()).delete(settings.milvus_collection, filter=f'doc_id == "{doc_id}"')
    try:
        (minio or get_minio()).remove_object(settings.minio_bucket, f"snapshots/{doc_id}.html")
    except Exception as e:
        logger.warning("删除 MinIO 快照失败(容错): %s", e)
    return True


async def _ingest(doc_id: str, url: str, payload: dict, mongo_db=None, milvus=None, minio=None, ingest_fn=None) -> None:
    title = payload["title"]
    content = payload["content"]
    column = payload.get("column") or "人工录入"
    category = payload.get("category") or classify_category(title, column)
    topics = payload.get("topics") or rule_tag_topics(title, content)
    publish_date = payload.get("publish_date") or datetime.now().strftime("%Y-%m-%d")
    expire_at = infer_expiry(title, content, category, publish_date)
    parsed = ParsedArticle(
        url=url, title=title, content=content, publish_date=publish_date,
        department=payload.get("department"), source_site="manual", column=column,
        raw_html=f"<html><head><title>{title}</title></head><body><h1>{title}</h1><p>{content}</p></body></html>",
    )
    await (ingest_fn or ingest_document)(parsed, category, topics, expire_at,
                                         mongo_db=mongo_db, milvus=milvus, minio=minio, doc_id=doc_id)
