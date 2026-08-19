import pytest

from collector import manual


class FakeDocsColl:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.deleted = []

    async def find_one(self, query):
        for d in self.docs:
            if d["doc_id"] == query.get("doc_id"):
                return d
        return None

    async def delete_many(self, query):
        self.deleted.append(query)
        return type("R", (), {"deleted_count": 1})()


class FakeDb:
    def __init__(self, docs=None):
        self.coll = FakeDocsColl(docs)

    def __getitem__(self, name):
        return self.coll


class FakeMilvus:
    def __init__(self):
        self.deleted = []

    def delete(self, coll, filter, **kw):
        self.deleted.append(filter)


class FakeMinio:
    def __init__(self, fail=False):
        self.fail = fail
        self.removed = []

    def remove_object(self, bucket, name):
        if self.fail:
            raise RuntimeError("minio down")
        self.removed.append(name)


async def fake_ingest(parsed, category, topics, expire_at, mongo_db=None, milvus=None, minio=None, doc_id=None):
    fake_ingest.calls.append({"parsed": parsed, "category": category, "topics": topics,
                              "expire_at": expire_at, "doc_id": doc_id})
    return doc_id


@pytest.mark.asyncio
async def test_create_uses_rules_and_manual_site():
    fake_ingest.calls = []
    doc_id = await manual.create_document({"title": "关于新生报到的通知", "content": "新生报到时间安排"},
                                          mongo_db=FakeDb(), milvus=FakeMilvus(), minio=FakeMinio(),
                                          ingest_fn=fake_ingest)
    assert len(doc_id) == 16
    call = fake_ingest.calls[0]
    assert call["doc_id"] == doc_id
    assert call["parsed"].source_site == "manual"
    assert call["parsed"].url == f"manual://{doc_id}"
    assert call["topics"] == ["新生入学"]  # 规则打标命中


@pytest.mark.asyncio
async def test_create_with_explicit_url_and_topic():
    fake_ingest.calls = []
    await manual.create_document({"title": "港澳学生住宿", "content": "...", "url": "https://x/y.htm",
                                  "topics": ["港澳生服务"]},
                                 mongo_db=FakeDb(), milvus=FakeMilvus(), minio=FakeMinio(),
                                 ingest_fn=fake_ingest)
    call = fake_ingest.calls[0]
    assert call["parsed"].url == "https://x/y.htm"
    assert call["topics"] == ["港澳生服务"]


@pytest.mark.asyncio
async def test_update_preserves_url_date_and_reuses_doc_id():
    fake_ingest.calls = []
    db = FakeDb([{"doc_id": "m1", "url": "https://x/old.htm", "publish_date": "2026-08-01",
                  "department": "教务处", "column": "通知公告"}])
    result = await manual.update_document("m1", {"title": "改标题", "content": "改内容"},
                                          mongo_db=db, milvus=FakeMilvus(), minio=FakeMinio(),
                                          ingest_fn=fake_ingest)
    assert result == "m1"
    call = fake_ingest.calls[0]
    assert call["doc_id"] == "m1"
    assert call["parsed"].url == "https://x/old.htm"
    assert call["parsed"].publish_date == "2026-08-01"


@pytest.mark.asyncio
async def test_update_missing_returns_none():
    result = await manual.update_document("nope", {"title": "x", "content": "y"},
                                          mongo_db=FakeDb(), milvus=FakeMilvus(), minio=FakeMinio(),
                                          ingest_fn=fake_ingest)
    assert result is None


@pytest.mark.asyncio
async def test_delete_cleans_three_stores():
    db, milvus, minio = FakeDb(), FakeMilvus(), FakeMinio()
    ok = await manual.delete_document("m1", mongo_db=db, milvus=milvus, minio=minio)
    assert ok is True
    assert db.coll.deleted == [{"doc_id": "m1"}]
    assert milvus.deleted == ['doc_id == "m1"']
    assert minio.removed == ["snapshots/m1.html"]


@pytest.mark.asyncio
async def test_delete_minio_down_tolerates():
    ok = await manual.delete_document("m1", mongo_db=FakeDb(), milvus=FakeMilvus(), minio=FakeMinio(fail=True))
    assert ok is True
