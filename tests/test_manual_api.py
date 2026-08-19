import httpx
import pytest

from collector.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_document_endpoint(client, monkeypatch):
    async def fake_create(payload):
        assert payload["title"] == "标题"
        return "m123"

    monkeypatch.setattr("collector.manual.create_document", fake_create)
    resp = await client.post("/api/admin/manual/documents", json={"title": "标题", "content": "正文"})
    assert resp.status_code == 200
    assert resp.json() == {"doc_id": "m123"}


async def test_create_missing_fields(client):
    resp = await client.post("/api/admin/manual/documents", json={"title": "", "content": ""})
    assert resp.status_code == 400


async def test_update_missing_returns_404(client, monkeypatch):
    async def fake_update(doc_id, payload):
        return None

    monkeypatch.setattr("collector.manual.update_document", fake_update)
    resp = await client.put("/api/admin/manual/documents/nope", json={"title": "x", "content": "y"})
    assert resp.status_code == 404


async def test_delete_document_endpoint(client, monkeypatch):
    async def fake_delete(doc_id):
        return True

    monkeypatch.setattr("collector.manual.delete_document", fake_delete)
    resp = await client.delete("/api/admin/manual/documents/m1")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}


async def test_parse_file_endpoint(client, monkeypatch):
    def fake_parse(filename, data):
        assert filename == "a.txt"
        return {"title": "a", "content": "内容"}

    monkeypatch.setattr("collector.parser.file_parser.parse_file", fake_parse)
    resp = await client.post("/api/admin/manual/parse-file", files={"file": ("a.txt", b"x", "text/plain")})
    assert resp.status_code == 200
    assert resp.json() == {"title": "a", "content": "内容"}
