# tests/test_admin_api.py
"""collector 管理端 API 测试：/health + 任务触发/查询（B8 评审遗留补齐）。"""
import asyncio

import httpx
import pytest

from collector.api import tasks as tasks_api
from collector.main import app
from collector.sources import SourceConfig


@pytest.fixture
async def client():
    # ASGITransport 不跑 lifespan → 调度器不启动、不触 Mongo
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_collector_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_trigger_run_creates_task(client, monkeypatch):
    source = SourceConfig(id="s1", name="主站公告", list_url="https://www.gzhu.edu.cn/z__l/tzgg.htm",
                          adapter="gzhu", enabled=True, interval_minutes=60)
    async def fake_list_all():
        return [source]
    monkeypatch.setattr("collector.sources.list_all_sources", fake_list_all)
    ran = []
    async def fake_run(s):
        ran.append(s.id)
        return {"task_id": "t1", "status": "running"}
    monkeypatch.setattr(tasks_api, "run_collection_task", fake_run)
    resp = await client.post("/api/admin/tasks/s1/run")
    assert resp.status_code == 200
    assert resp.json() == {"started": True, "source_id": "s1"}
    await asyncio.sleep(0)  # 让 create_task 的协程执行
    assert ran == ["s1"]


async def test_trigger_run_unknown_source(client, monkeypatch):
    async def fake_list_all():
        return []
    monkeypatch.setattr("collector.sources.list_all_sources", fake_list_all)
    resp = await client.post("/api/admin/tasks/nope/run")
    assert resp.status_code == 200
    assert resp.json() == {"error": "采集源不存在"}


async def test_list_tasks(client, monkeypatch):
    class FakeCursor:
        def __init__(self, items):
            self._items = items
        def sort(self, *a, **k):
            return self
        def limit(self, n):
            return self
        def __aiter__(self):
            self._it = iter(self._items)
            return self
        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    class FakeTasksColl:
        def find(self, query):
            return FakeCursor([{"task_id": "t1", "source_id": "s1", "status": "success"}])

    class FakeDb:
        def __getitem__(self, name):
            return FakeTasksColl()

    monkeypatch.setattr(tasks_api, "get_mongo", lambda: FakeDb())
    resp = await client.get("/api/admin/tasks?source_id=s1")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1 and items[0]["task_id"] == "t1"
