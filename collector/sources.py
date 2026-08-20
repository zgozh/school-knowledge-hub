"""采集源配置 CRUD（MongoDB sources 集合）。"""
import uuid
from dataclasses import asdict, dataclass

from shared.clients import get_mongo
from shared.logging import get_logger

logger = get_logger("collector.sources")

ADAPTERS = {"gzhu": "collector.crawler.gzhu.GUZhuAdapter", "gznews": "collector.crawler.gznews.GUNewsAdapter"}


@dataclass
class SourceConfig:
    id: str
    name: str
    list_url: str
    adapter: str
    enabled: bool = True
    interval_minutes: int = 360
    max_pages: int = 1   # 1/3/5/10/0；0 = 「全部」（内部封顶 50 页）

    @staticmethod
    def from_dict(d: dict) -> "SourceConfig":
        return SourceConfig(id=d["id"], name=d["name"], list_url=d["list_url"],
                            adapter=d["adapter"], enabled=d.get("enabled", True),
                            interval_minutes=d.get("interval_minutes", 360),
                            max_pages=d.get("max_pages", 1))


async def list_sources() -> list[SourceConfig]:
    db = get_mongo()
    docs = db["sources"].find({"enabled": True})
    return [SourceConfig.from_dict(d) async for d in docs]


async def list_all_sources() -> list[SourceConfig]:
    db = get_mongo()
    docs = db["sources"].find()
    return [SourceConfig.from_dict(d) async for d in docs]


async def save_source(cfg: SourceConfig) -> str:
    if not cfg.id:
        cfg.id = uuid.uuid4().hex[:12]
    await get_mongo()["sources"].update_one({"id": cfg.id}, {"$set": asdict(cfg)}, upsert=True)
    return cfg.id


async def delete_source(source_id: str) -> bool:
    result = await get_mongo()["sources"].delete_one({"id": source_id})
    return result.deleted_count > 0
