# tests/test_sources.py
"""SourceConfig.max_pages 字段 + create_source 透传测试。"""
import httpx
import pytest

from collector.api import sources as sources_api
from collector.main import app
from collector.sources import SourceConfig


def test_from_dict_defaults_max_pages_to_1():
    cfg = SourceConfig.from_dict({"id": "s1", "name": "主站公告", "list_url": "https://x/list.htm",
                                  "adapter": "gzhu"})
    assert cfg.max_pages == 1


def test_from_dict_reads_explicit_max_pages():
    cfg = SourceConfig.from_dict({"id": "s1", "name": "主站公告", "list_url": "https://x/list.htm",
                                  "adapter": "gzhu", "max_pages": 3})
    assert cfg.max_pages == 3


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_source_passes_max_pages(client, monkeypatch):
    captured = []
    async def fake_save(cfg):
        captured.append(cfg)
        return "s1"
    monkeypatch.setattr(sources_api.sources, "save_source", fake_save)
    resp = await client.post("/api/admin/sources", json={
        "name": "主站公告", "list_url": "https://x/list.htm", "adapter": "gzhu", "max_pages": 5,
    })
    assert resp.status_code == 200
    assert captured[0].max_pages == 5


async def test_create_source_defaults_max_pages_to_1(client, monkeypatch):
    captured = []
    async def fake_save(cfg):
        captured.append(cfg)
        return "s1"
    monkeypatch.setattr(sources_api.sources, "save_source", fake_save)
    resp = await client.post("/api/admin/sources", json={
        "name": "主站公告", "list_url": "https://x/list.htm", "adapter": "gzhu",
    })
    assert resp.status_code == 200
    assert captured[0].max_pages == 1
