# tests/test_scheduler.py
"""调度器装配测试（B7 评审遗留补齐）：enabled 采集源注册周期任务。"""
from collector import scheduler as sched_mod
from collector.sources import SourceConfig


async def test_start_scheduler_registers_enabled_sources(monkeypatch):
    source = SourceConfig(id="s1", name="主站公告", list_url="https://www.gzhu.edu.cn/z__l/tzgg.htm",
                          adapter="gzhu", enabled=True, interval_minutes=360)
    async def fake_list_sources():
        return [source]
    monkeypatch.setattr(sched_mod, "list_sources", fake_list_sources)
    try:
        await sched_mod.start_scheduler()
        jobs = sched_mod._scheduler.get_jobs()
        assert any(j.id == f"collect-{source.id}" for j in jobs)
    finally:
        sched_mod.stop_scheduler()


async def test_start_scheduler_second_call_is_noop(monkeypatch):
    async def fake_list_sources():
        return []
    monkeypatch.setattr(sched_mod, "list_sources", fake_list_sources)
    try:
        await sched_mod.start_scheduler()
        first = sched_mod._scheduler
        await sched_mod.start_scheduler()
        assert sched_mod._scheduler is first  # 幂等，不重复装配
    finally:
        sched_mod.stop_scheduler()
