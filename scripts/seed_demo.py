"""演示模拟数据播种：六大专题域模板 → 真实分类/打标/时效/三写入库管线（幂等可重跑）。

用法：uv run python -m scripts.seed_demo
前置：docker 存储（Milvus/Mongo/MinIO）+ model_server:8001 在线。
"""
import asyncio

from collector.ingest.writer import ingest_document
from collector.lifecycle.validity import infer_expiry
from collector.parser.extract import ParsedArticle
from collector.tagger.rules import classify_category, rule_tag_topics
from scripts.demo_templates import DEMO_ARTICLES
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("scripts.seed_demo")


def _ensure_bucket(minio=None) -> None:
    """MinIO 桶不存在则创建（空环境首次运行必需）；失败仅告警不阻断。"""
    from shared.clients import get_minio

    try:
        m = minio or get_minio()
        if not m.bucket_exists(settings.minio_bucket):
            m.make_bucket(settings.minio_bucket)
    except Exception as e:
        logger.warning("MinIO 桶检查失败(降级): %s", e)


async def seed_all() -> int:
    _ensure_bucket()
    for i, t in enumerate(DEMO_ARTICLES):
        url = f"https://demo.gzhu.edu.cn/demo/{i + 1:02d}.htm"
        parsed = ParsedArticle(
            url=url, title=t.title, content=t.content, publish_date=t.publish_date,
            department=t.department, source_site="demo", column=t.column,
            raw_html=(f"<html><head><title>{t.title}</title></head><body>"
                      f"<h1>{t.title}</h1><div class='content'>{t.content}</div></body></html>"),
        )
        category = classify_category(t.title, t.column)
        topics = rule_tag_topics(t.title, t.content) or [t.topic]
        expire_at = infer_expiry(t.title, t.content, category, t.publish_date)
        await ingest_document(parsed, category, topics, expire_at)
        logger.info("已播种 [%s] %s", t.topic, t.title)
    return len(DEMO_ARTICLES)


async def demo_doc_count() -> int:
    from shared.clients import get_mongo

    db = get_mongo()
    n = 0
    async for _ in db["documents"].find({"url": {"$regex": "^https://demo.gzhu.edu.cn/demo/"}}):
        n += 1
    return n


if __name__ == "__main__":
    seeded = asyncio.run(seed_all())
    print(f"播种完成：{seeded} 篇；库内演示文档总数：{asyncio.run(demo_doc_count())}")
