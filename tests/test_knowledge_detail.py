# tests/test_knowledge_detail.py
"""知识库单篇详情端点测试：Mongo 元数据 + 从 Milvus 拼正文（TDD）。"""
import httpx
import pytest

from collector.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _patch_storage(monkeypatch, doc, rows):
    class FakeDocsColl:
        async def find_one(self, query):
            return dict(doc) if doc else None

    class FakeDb:
        def __getitem__(self, name):
            return FakeDocsColl()

    class FakeMilvus:
        def query(self, coll, filter=None, output_fields=None):
            return list(rows)

    monkeypatch.setattr("shared.clients.get_mongo", lambda: FakeDb())
    monkeypatch.setattr("shared.clients.get_milvus", lambda: FakeMilvus())


async def test_get_document_detail_returns_meta_and_content(client, monkeypatch):
    _patch_storage(
        monkeypatch,
        {"doc_id": "d1", "url": "https://demo.gzhu.edu.cn/demo/01.htm",
         "title": "新生报到通知", "source_site": "demo", "topics": ["新生入学"]},
        [{"chunk_idx": 1, "text": "第二段"}, {"chunk_idx": 0, "text": "第一段"}],
    )
    resp = await client.get("/api/admin/knowledge/d1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "新生报到通知"
    assert data["content"] == "第一段\n第二段"  # 按 chunk_idx 排序拼接


async def test_get_document_detail_not_found(client, monkeypatch):
    _patch_storage(monkeypatch, None, [])
    resp = await client.get("/api/admin/knowledge/nope")
    assert resp.status_code == 404
