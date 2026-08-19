"""采集任务状态机：pending→running→success/partial/failed；逐页隔离；重试 3 次。"""
import asyncio
from datetime import datetime

from collector.crawler.engine import CrawlEngine
from collector.lifecycle.validity import infer_expiry
from collector.parser.extract import extract_article
from collector.sources import SourceConfig
from collector.tagger.llm_topics import batch_tag_topics
from collector.tagger.rules import classify_category, rule_tag_topics
from shared.clients import get_mongo
from shared.errors import ExternalServiceError
from shared.logging import get_logger
from shared.retry import async_retry

logger = get_logger("collector.tasks")

ADAPTER_IMPORT = {
    "gzhu": "collector.crawler.gzhu",
    "gznews": "collector.crawler.gznews",
}


def _load_adapter(name: str):
    module = __import__(ADAPTER_IMPORT[name], fromlist=["*"])
    return module.GUZhuAdapter() if name == "gzhu" else module.GUNewsAdapter()


@async_retry(retries=3, base_delay=2.0, max_delay=30.0)
async def _fetch_with_retry(engine: CrawlEngine, source: SourceConfig):
    return await engine.fetch_source(source.list_url, _load_adapter(source.adapter))


async def run_collection_task(source: SourceConfig) -> dict:
    """执行一次采集任务，状态写入 MongoDB task_runs。"""
    from collector.ingest.writer import ingest_document

    db = get_mongo()
    task_id = f"{source.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    run_doc = {"task_id": task_id, "source_id": source.id, "status": "running",
               "started_at": datetime.now().isoformat(), "succeeded": 0, "failed": 0, "failures": []}
    await db["task_runs"].insert_one(run_doc)
    logger.info("任务开始 %s", task_id)

    engine = CrawlEngine()
    try:
        raw_articles, failures = await _fetch_with_retry(engine, source)
    except ExternalServiceError as e:
        await db["task_runs"].update_one({"task_id": task_id},
                                         {"$set": {"status": "failed", "finished_at": datetime.now().isoformat(),
                                                   "error": str(e)}})
        return {"task_id": task_id, "status": "failed", "succeeded": 0, "failed": 0}
    finally:
        await engine.close()

    parsed = []
    for raw in raw_articles:
        try:
            parsed.append(extract_article(raw))
        except ExternalServiceError as e:
            failures.append({"url": raw.url, "error": str(e), "stage": "parse"})

    topics_map = await batch_tag_topics(parsed)
    succeeded = 0
    for art in parsed:
        try:
            category = classify_category(art.title, art.column)
            topics = topics_map.get(art.url) or rule_tag_topics(art.title, art.content)
            expire_at = infer_expiry(art.title, art.content, category, art.publish_date or "")
            await ingest_document(art, category, topics, expire_at)
            succeeded += 1
        except Exception as e:
            failures.append({"url": art.url, "error": str(e), "stage": "ingest"})

    # 页面级失败→partial；任务级彻底失败（fetch 抛异常）已在上方早退分支返回 failed
    status = "success" if not failures else "partial"
    await db["task_runs"].update_one({"task_id": task_id},
                                     {"$set": {"status": status, "succeeded": succeeded,
                                               "failed": len(failures), "failures": failures,
                                               "finished_at": datetime.now().isoformat()}})
    logger.info("任务结束 %s status=%s 成功=%d 失败=%d", task_id, status, succeeded, len(failures))
    return {"task_id": task_id, "status": status, "succeeded": succeeded, "failed": len(failures)}
