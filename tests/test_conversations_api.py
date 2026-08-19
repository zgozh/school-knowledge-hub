# tests/test_conversations_api.py
"""会话 API 端点测试（monkeypatch 业务函数）。"""
import httpx
import pytest

from qa_api.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_list_conversations_endpoint(client, monkeypatch):
    async def fake_list(db):
        return [{"conversation_id": "c1", "title": "t", "updated_at": "", "message_count": 1}]
    monkeypatch.setattr("qa_api.api.conversations._list", fake_list)
    resp = await client.get("/api/conversations")
    assert resp.status_code == 200
    assert resp.json()[0]["conversation_id"] == "c1"


async def test_get_conversation_endpoint(client, monkeypatch):
    async def fake_get(db, cid):
        assert cid == "c1"
        return {"conversation_id": "c1", "messages": []}
    monkeypatch.setattr("qa_api.api.conversations._get", fake_get)
    resp = await client.get("/api/conversations/c1")
    assert resp.status_code == 200
    assert resp.json()["conversation_id"] == "c1"


async def test_get_conversation_404(client, monkeypatch):
    async def fake_get(db, cid):
        return None
    monkeypatch.setattr("qa_api.api.conversations._get", fake_get)
    resp = await client.get("/api/conversations/nope")
    assert resp.status_code == 404


async def test_delete_conversation_endpoint(client, monkeypatch):
    async def fake_delete(db, cid):
        assert cid == "c1"
        return True
    monkeypatch.setattr("qa_api.api.conversations._delete", fake_delete)
    resp = await client.delete("/api/conversations/c1")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}
