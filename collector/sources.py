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

    @staticmethod
    def from_dict(d: dict) -> "SourceConfig":
        return SourceConfig(id=d["id"], name=d["name"], list_url=d["list_url"],
                            adapter=d["adapter"], enabled=d.get("enabled", True),
                            interval_minutes=d.get("interval_minutes", 360))


def list_sources() -> list[SourceConfig]:
    db = get_mongo()
    docs = db["sources"].find({"enabled": True})
    return [SourceConfig.from_dict(d) for d in docs]


def list_all_sources() -> list[SourceConfig]:
    db = get_mongo()
    docs = db["sources"].find()
    return [SourceConfig.from_dict(d) for d in docs]


def save_source(cfg: SourceConfig) -> str:
    if not cfg.id:
        cfg.id = uuid.uuid4().hex[:12]
    get_mongo()["sources"].update_one({"id": cfg.id}, {"$set": asdict(cfg)}, upsert=True)
    return cfg.id


def delete_source(source_id: str) -> bool:
    result = get_mongo()["sources"].delete_one({"id": source_id})
    return result.deleted_count > 0
