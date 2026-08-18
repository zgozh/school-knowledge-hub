"""知识库管理：查询/上下架/统计/到期检测。（motor 异步：所有 Mongo 调用必须 await）"""
from datetime import datetime

from shared.clients import get_mongo
from shared.logging import get_logger

logger = get_logger("collector.knowledge")


async def query_documents(status: str | None = None, category: str | None = None, topic: str | None = None,
                          page: int = 1, page_size: int = 20) -> dict:
    query = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if topic:
        query["topics"] = topic
    collection = get_mongo()["documents"]
    total = await collection.count_documents(query)
    cursor = collection.find(query).sort("ingested_at", -1).skip((page - 1) * page_size).limit(page_size)
    items = []
    async for d in cursor:
        d.pop("_id", None)
        items.append(d)
    return {"items": items, "total": total}


async def set_doc_status(doc_id: str, status: str) -> bool:
    """人工上下架：更新 Mongo 状态；Milvus 状态在检索侧按 Mongo 状态过滤（简化版）。"""
    assert status in ("active", "archived")
    result = await get_mongo()["documents"].update_one({"doc_id": doc_id}, {"$set": {"status": status}})
    return result.matched_count > 0


async def check_expiry() -> int:
    """到期检测：expire_at 已过且仍为 active 的文档置为 expired。返回数量。"""
    collection = get_mongo()["documents"]
    now_str = datetime.now().strftime("%Y-%m-%d")
    result = await collection.update_many(
        {"expire_at": {"$ne": None, "$lt": now_str}, "status": "active"},
        {"$set": {"status": "expired"}},
    )
    return result.modified_count


async def asset_stats() -> dict:
    db = get_mongo()
    docs = db["documents"]
    total = await docs.count_documents({})
    by_category = {}
    async for d in docs.aggregate([{"$group": {"_id": "$category", "count": {"$sum": 1}}}]):
        by_category[d["_id"]] = d["count"]
    by_status = {}
    async for d in docs.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
        by_status[d["_id"]] = d["count"]
    by_topic = {}
    async for d in docs.aggregate([{"$unwind": {"path": "$topics", "preserveNullAndEmptyArrays": True}},
                                   {"$group": {"_id": "$topics", "count": {"$sum": 1}}}]):
        by_topic[str(d["_id"])] = d["count"]
    recent_tasks = []
    cursor = db["task_runs"].find().sort("started_at", -1).limit(5)
    async for t in cursor:
        t.pop("_id", None)
        recent_tasks.append(t)
    # 问答热度（反哺"该采集什么"）
    qa_logs = db["qa_logs"]
    qa_total = await qa_logs.count_documents({})
    hot_queries = []
    async for d in qa_logs.aggregate([{"$group": {"_id": "$query", "count": {"$sum": 1}}},
                                      {"$sort": {"count": -1}}, {"$limit": 5}]):
        hot_queries.append({"query": d["_id"], "count": d["count"]})
    return {"total_docs": total, "by_category": by_category, "by_status": by_status,
            "by_topic": by_topic, "recent_tasks": recent_tasks,
            "qa_total": qa_total, "hot_queries": hot_queries}
