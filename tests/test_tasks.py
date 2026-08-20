from unittest.mock import AsyncMock

from collector import tasks as tasks_mod


def _fake_mongo():
    fake = AsyncMock()
    fake.insert_one = AsyncMock()
    fake.update_one = AsyncMock()
    fake.__getitem__.return_value = fake
    return fake


async def test_run_task_partial_failure(monkeypatch):
    """单页失败→部分失败状态；结果记录成功/失败数。"""
    fake_engine = AsyncMock()
    fake_engine.fetch_source = AsyncMock(return_value=([], [{"url": "https://x/1.htm", "error": "超时"}], False))
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: fake_engine)
    monkeypatch.setattr(tasks_mod, "get_mongo", lambda: _fake_mongo())
    source = tasks_mod.SourceConfig(id="s1", name="主站公告", list_url="https://www.gzhu.edu.cn/z__l/tzgg.htm",
                                    adapter="gzhu", enabled=True, interval_minutes=60)
    result = await tasks_mod.run_collection_task(source)
    assert result["status"] == "partial"
    assert result["failed"] == 1
    assert result["succeeded"] == 0
    assert result["page_capped"] is False


async def test_run_task_passes_max_pages_and_records_capped(monkeypatch):
    """fetch_source 收到 source.max_pages；page_capped 记入返回结果与 task_runs。"""
    fake_engine = AsyncMock()
    fake_engine.fetch_source = AsyncMock(return_value=([], [], True))
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: fake_engine)
    fake_mongo = _fake_mongo()
    monkeypatch.setattr(tasks_mod, "get_mongo", lambda: fake_mongo)
    source = tasks_mod.SourceConfig(id="s1", name="x", list_url="https://x/list.htm",
                                    adapter="gzhu", enabled=True, interval_minutes=60, max_pages=3)
    result = await tasks_mod.run_collection_task(source)
    # 透传 max_pages 到 fetch_source（第 3 个位置参数）
    assert fake_engine.fetch_source.await_args.args[2] == 3
    assert result["page_capped"] is True
    # task_runs 更新带 page_capped
    update_call = fake_mongo.update_one.await_args
    assert update_call.args[1]["$set"]["page_capped"] is True
