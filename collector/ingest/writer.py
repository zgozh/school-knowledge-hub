"""三写入库：切分→向量化→Milvus 向量 + MongoDB 元数据 + MinIO 快照（幂等：先删后插）。"""
import hashlib
from datetime import datetime

from collector.ingest.splitter import split_text
from collector.parser.extract import ParsedArticle
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("collector.ingest")


def doc_id_of(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def ensure_collection(milvus) -> None:
    """创建双向量集合（dense COSINE + sparse IP）与索引并加载；已存在则确保加载。"""
    name = settings.milvus_collection
    if milvus.has_collection(name):
        milvus.load_collection(name)  # 幂等：确保已加载
        return
    from pymilvus import CollectionSchema, DataType, FieldSchema

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="chunk_idx", dtype=DataType.INT64),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=1024),
        FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
        FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="topics", dtype=DataType.ARRAY, element_type=DataType.VARCHAR, max_capacity=16, max_length=32),
        FieldSchema(name="publish_date", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="expire_at", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=16),
        FieldSchema(name="ingested_ts", dtype=DataType.INT64),
    ]
    milvus.create_collection(
        collection_name=name,
        schema=CollectionSchema(fields, description="校务知识分块向量"),
    )
    index_params = milvus.prepare_index_params()
    # AUTOINDEX：小数据量自动暴力检索，避免 IVF nlist 过大导致 nprobe 探不到桶（空召回）
    index_params.add_index(field_name="dense_vector", index_type="AUTOINDEX", metric_type="COSINE")
    index_params.add_index(field_name="sparse_vector", index_type="SPARSE_INVERTED_INDEX",
                           metric_type="IP")
    milvus.create_index(name, index_params)
    milvus.load_collection(name)
    logger.info("已创建集合 %s", name)


async def ingest_document(parsed: ParsedArticle, category: str, topics: list[str], expire_at: str | None,
                          embed_fn=None, milvus=None, mongo_db=None, minio=None) -> str:
    """幂等入库：先按 doc_id 删除旧数据再插入新数据。返回 doc_id。（motor 异步，所有 Mongo 调用必须 await）"""
    from shared.clients import get_milvus, get_minio, get_mongo

    milvus = milvus or get_milvus()
    mongo_db = mongo_db or get_mongo()
    minio = minio or get_minio()
    embed_fn = embed_fn or _embed_batch
    ensure_collection(milvus)

    doc_id = doc_id_of(parsed.url)
    chunks = split_text(parsed.content)
    embeddings = embed_fn(chunks)

    # 幂等：先删后插
    milvus.delete(settings.milvus_collection, filter=f'doc_id == "{doc_id}"')
    collection = mongo_db["documents"]
    existing = await collection.find_one({"doc_id": doc_id})
    if existing:
        await collection.delete_many({"doc_id": doc_id})

    # MinIO 快照（降级：失败标记缺失）
    snapshot_missing = False
    try:
        import io

        data = parsed.raw_html.encode()
        minio.put_object(settings.minio_bucket, f"snapshots/{doc_id}.html",
                         io.BytesIO(data), len(data), content_type="text/html")
    except Exception as e:
        logger.warning("MinIO 快照失败(降级): %s", e)
        snapshot_missing = True

    # MongoDB 元数据
    meta = {
        "doc_id": doc_id,
        "url": parsed.url,
        "title": parsed.title,
        "publish_date": parsed.publish_date,
        "department": parsed.department,
        "source_site": parsed.source_site,
        "column": parsed.column,
        "category": category,
        "topics": topics,
        "expire_at": expire_at,
        "status": "active",
        "snapshot_missing": snapshot_missing,
        "chunk_count": len(chunks),
        "ingested_at": datetime.now().isoformat(),
    }
    await collection.insert_one(meta)

    # Milvus 向量（每个 chunk 一行）
    rows = []
    now_ts = int(datetime.now().timestamp())
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        rows.append({
            "id": f"{doc_id}_{i}",
            "doc_id": doc_id,
            "chunk_idx": i,
            "text": chunk,
            "dense_vector": emb["dense"],
            "sparse_vector": emb["sparse"],
            "category": category,
            "topics": topics,
            "publish_date": parsed.publish_date or "",
            "expire_at": expire_at or "",
            "status": "active",
            "ingested_ts": now_ts,
        })
    if rows:
        milvus.insert(settings.milvus_collection, rows)
    logger.info("入库完成 doc=%s chunks=%d", doc_id, len(chunks))
    return doc_id


def _embed_batch(texts: list[str]) -> list[dict]:
    import httpx

    resp = httpx.post(f"{settings.embed_service_url}/embed", json={"texts": texts},
                      timeout=settings.external_timeout)
    resp.raise_for_status()
    return resp.json()["embeddings"]
