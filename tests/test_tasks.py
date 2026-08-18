from unittest.mock import AsyncMock

from collector import tasks as tasks_mod


async def test_run_task_partial_failure(monkeypatch):
    """单页失败→部分失败状态；结果记录成功/失败数。"""
    fake_engine = AsyncMock()
    fake_engine.fetch_source = AsyncMock(return_value=([], [{"url": "https://x/1.htm", "error": "超时"}]))
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: fake_engine)
    fake_mongo = AsyncMock()
    fake_mongo.find_one = AsyncMock(return_value=None)
    fake_mongo.insert_one = AsyncMock()
    fake_mongo.update_one = AsyncMock()
    # db["task_runs"] 返回 fake_mongo 自身，使下述显式 AsyncMock 设置生效
    fake_mongo.__getitem__.return_value = fake_mongo
    monkeypatch.setattr(tasks_mod, "get_mongo", lambda: fake_mongo)
    source = tasks_mod.SourceConfig(id="s1", name="主站公告", list_url="https://www.gzhu.edu.cn/z__l/tzgg.htm",
                                    adapter="gzhu", enabled=True, interval_minutes=60)
    result = await tasks_mod.run_collection_task(source)
    assert result["status"] == "partial"
    assert result["failed"] == 1
    assert result["succeeded"] == 0
