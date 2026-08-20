# collector/api/sources.py
"""采集源管理 API。"""
from fastapi import APIRouter

from collector import sources
from collector.sources import SourceConfig

router = APIRouter(prefix="/api/admin/sources", tags=["采集源"])


@router.get("")
async def get_sources():
    return {"items": [s.__dict__ for s in await sources.list_all_sources()]}


@router.post("")
async def create_source(payload: dict):
    cfg = SourceConfig(id="", name=payload["name"], list_url=payload["list_url"],
                       adapter=payload["adapter"], enabled=payload.get("enabled", True),
                       interval_minutes=payload.get("interval_minutes", 360),
                       max_pages=payload.get("max_pages", 1))
    return {"id": await sources.save_source(cfg)}


@router.delete("/{source_id}")
async def remove_source(source_id: str):
    return {"deleted": await sources.delete_source(source_id)}
