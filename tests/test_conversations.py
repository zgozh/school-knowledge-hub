# tests/test_conversations.py
"""会话业务函数测试（纯 mock Mongo，依赖注入 db）。"""
from qa_api.conversations import (
    append_or_create, delete_conversation, get_conversation, list_conversations,
)


class FakeCursor:
    def __init__(self, items):
        self._items = items
    def sort(self, *a, **k):
        return self
    async def to_list(self, n):
        return self._items


class FakeConvColl:
    def __init__(self, docs=None):
        self.docs = docs or {}
        self.inserted = []
        self.updated = []
    def find(self, query):
        return FakeCursor(list(self.docs.values()))
    async def find_one(self, query):
        return self.docs.get(query.get("conversation_id"))
    async def insert_one(self, doc):
        self.inserted.append(doc)
        self.docs[doc["conversation_id"]] = doc
    async def update_one(self, query, update):
        self.updated.append((query, update))
        doc = self.docs.get(query.get("conversation_id"))
        if doc is not None:
            for key, spec in update.get("$push", {}).items():
                doc.setdefault(key, []).extend(spec.get("$each", []))
            doc.update(update.get("$set", {}))
    async def delete_many(self, query):
        self.docs.pop(query.get("conversation_id"), None)


class FakeDb:
    def __init__(self, coll=None):
        self.coll = coll or FakeConvColl()
    def __getitem__(self, name):
        return self.coll


async def test_list_conversations_returns_summary_without_messages():
    coll = FakeConvColl({"c1": {
        "conversation_id": "c1", "title": "标题1", "updated_at": "2026-08-20 10:00:00",
        "messages": [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}],
    }})
    items = await list_conversations(FakeDb(coll))
    assert len(items) == 1
    assert items[0]["conversation_id"] == "c1"
    assert items[0]["message_count"] == 2
    assert "messages" not in items[0]


async def test_get_conversation_found_and_missing():
    coll = FakeConvColl({"c1": {"conversation_id": "c1"}})
    db = FakeDb(coll)
    assert (await get_conversation(db, "c1"))["conversation_id"] == "c1"
    assert await get_conversation(db, "nope") is None


async def test_delete_conversation_returns_true():
    coll = FakeConvColl({"c1": {"conversation_id": "c1"}})
    assert await delete_conversation(FakeDb(coll), "c1") is True


async def test_append_or_create_new_conversation():
    db = FakeDb()
    cid = await append_or_create(db, None, "新生报到需要什么材料", "答案", [{"doc_id": "d1"}])
    assert len(cid) == 16
    doc = db.coll.inserted[0]
    assert doc["title"] == "新生报到需要什么材料"
    assert len(doc["messages"]) == 2
    assert doc["messages"][0]["role"] == "user"
    assert doc["messages"][1]["sources"] == [{"doc_id": "d1"}]
    assert doc["created_at"] and doc["updated_at"]


async def test_append_or_create_title_truncated_to_20_chars():
    db = FakeDb()
    await append_or_create(db, None, "这是一个超过二十个字的很长很长很长很长的提问", "答", [])
    assert db.coll.inserted[0]["title"].endswith("…")
    assert len(db.coll.inserted[0]["title"]) == 21  # 20 字 + 省略号


async def test_append_or_create_existing_appends_and_keeps_title():
    coll = FakeConvColl({"c1": {"conversation_id": "c1", "title": "旧标题", "messages": []}})
    db = FakeDb(coll)
    cid = await append_or_create(db, "c1", "追问", "答案2", [])
    assert cid == "c1"
    assert coll.updated and not coll.inserted
    assert coll.docs["c1"]["title"] == "旧标题"
    assert len(coll.docs["c1"]["messages"]) == 2


async def test_append_or_create_unknown_id_creates_new():
    db = FakeDb()
    cid = await append_or_create(db, "ghost", "问", "答", [])
    assert len(cid) == 16 and db.coll.inserted
