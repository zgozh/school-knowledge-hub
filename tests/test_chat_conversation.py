# tests/test_chat_conversation.py
"""/chat 会话落库测试：首条建会话、带 id 追加、无效 id 建新、done 返回 id。"""
import json

import httpx
import pytest

from qa_api.main import app
from qa_api.retriever.hybrid import ScoredChunk


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class FakeConvColl:
    def __init__(self, docs=None):
        self.docs = docs or {}
        self.inserted = []
        self.updated = []
    async def find_one(self, query):
        return self.docs.get(query.get("conversation_id"))
    async def insert_one(self, doc):
        self.inserted.append(doc)
        self.docs[doc["conversation_id"]] = doc
    async def update_one(self, query, update):
        self.updated.append((query, update))
    async def delete_many(self, query):
        self.docs.pop(query.get("conversation_id"), None)


class FakeDocsColl:
    async def find_one(self, query):
        return {"doc_id": query.get("doc_id"), "title": "文档", "url": "https://x/y",
                "publish_date": "2026-08-20", "category": "教务", "expired": False}
    async def insert_one(self, doc):
        pass  # qa_logs 写入用，no-op


class FakeDb:
    def __init__(self):
        self.conversations = FakeConvColl()
        self.documents = FakeDocsColl()
        self.qa_logs = FakeDocsColl()
    def __getitem__(self, name):
        return getattr(self, name)


def _chunk():
    return ScoredChunk(chunk_id="c1", doc_id="d1", text="正文", score=0.9,
                       dense_score=0.9, sparse_score=0.0, category="教务",
                       publish_date="2026-08-20", expired=False)


def _install_mocks(monkeypatch, db):
    import qa_api.api.chat as chat_mod

    async def fake_hybrid(query, topics=None):
        return [_chunk()]

    async def fake_stream(query, context, history=None):
        yield "这是"
        yield "答案"

    monkeypatch.setattr(chat_mod, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(chat_mod, "rerank_chunks", lambda q, c: c)
    monkeypatch.setattr(chat_mod, "cliff_cutoff", lambda c: c)
    monkeypatch.setattr(chat_mod, "stream_answer", fake_stream)
    monkeypatch.setattr(chat_mod, "get_mongo", lambda: db)


def _parse_done(body):
    body = body.replace("\r\n", "\n")
    for block in body.split("\n\n"):
        if block.startswith("event: done"):
            for line in block.split("\n"):
                if line.startswith("data:"):
                    return json.loads(line[len("data:"):].strip())
    return None


async def test_first_message_creates_conversation(client, monkeypatch):
    db = FakeDb()
    _install_mocks(monkeypatch, db)
    resp = await client.post("/api/chat", json={"query": "新生报到需要什么材料", "conversation_id": None})
    done = _parse_done(resp.text)
    assert done and done["conversation_id"]
    assert len(db.conversations.inserted) == 1
    assert db.conversations.inserted[0]["title"].startswith("新生报到需要什么材料")
    assert len(db.conversations.inserted[0]["messages"]) == 2


async def test_with_conversation_id_appends_not_creates(client, monkeypatch):
    db = FakeDb()
    db.conversations.docs["c1"] = {"conversation_id": "c1", "title": "旧标题", "messages": []}
    _install_mocks(monkeypatch, db)
    resp = await client.post("/api/chat", json={"query": "追问", "conversation_id": "c1"})
    done = _parse_done(resp.text)
    assert done["conversation_id"] == "c1"
    assert db.conversations.updated and not db.conversations.inserted


async def test_unknown_conversation_id_creates_new(client, monkeypatch):
    db = FakeDb()
    _install_mocks(monkeypatch, db)
    resp = await client.post("/api/chat", json={"query": "问", "conversation_id": "ghost"})
    done = _parse_done(resp.text)
    assert done["conversation_id"]
    assert len(db.conversations.inserted) == 1
