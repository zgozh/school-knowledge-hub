"""APScheduler 装配：enabled 采集源注册周期任务。"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from collector.sources import list_sources
from collector.tasks import run_collection_task
from shared.logging import get_logger

logger = get_logger("collector.scheduler")
_scheduler: AsyncIOScheduler | None = None


async def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    for source in await list_sources():
        _scheduler.add_job(
            run_collection_task, IntervalTrigger(minutes=source.interval_minutes),
            args=[source], id=f"collect-{source.id}", replace_existing=True,
        )
    _scheduler.start()
    logger.info("调度器已启动，共 %d 个采集源", len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
