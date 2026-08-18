# collector/api/tasks.py
"""采集任务触发与查询 API。"""
import asyncio

from fastapi import APIRouter

from collector import sources
from collector.tasks import run_collection_task
from shared.clients import get_mongo

router = APIRouter(prefix="/api/admin/tasks", tags=["采集任务"])


@router.post("/{source_id}/run")
async def trigger_run(source_id: str):
    target = next((s for s in await sources.list_all_sources() if s.id == source_id), None)
    if target is None:
        return {"error": "采集源不存在"}
    asyncio.create_task(run_collection_task(target))
    return {"started": True, "source_id": source_id}


@router.get("")
async def list_tasks(source_id: str | None = None, limit: int = 20):
    query = {"source_id": source_id} if source_id else {}
    items = []
    cursor = get_mongo()["task_runs"].find(query).sort("started_at", -1).limit(limit)
    async for t in cursor:
        t.pop("_id", None)
        items.append(t)
    return {"items": items}
