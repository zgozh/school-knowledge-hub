import pytest

from collector.parser.extract import ParsedArticle
from collector.ingest.writer import ingest_document


class FakeMilvus:
    def __init__(self):
        self.rows = []
        self.deleted = []

    def has_collection(self, name):
        return True  # 模拟集合已存在（ensure_collection 走"确保加载"分支）

    def load_collection(self, name):
        pass  # 模拟已加载

    def delete(self, collection_name, filter, **kwargs):
        self.deleted.append(filter)
        return {"delete_count": len(self.rows)}

    def insert(self, collection_name, data, **kwargs):
        self.rows.extend(data)
        return {"insert_count": len(data)}


class FakeMongo:
    def __init__(self):
        self.docs = []

    def __getitem__(self, name):
        # 模拟 motor 数据库的 db["documents"] 取集合（fake 自身即 documents 集合）
        return self

    async def find_one(self, query):
        for d in self.docs:
            if d["doc_id"] == query.get("doc_id"):
                return d
        return None

    async def delete_many(self, query):
        n = len(self.docs)
        self.docs = [d for d in self.docs if d["doc_id"] != query.get("doc_id")]
        return type("R", (), {"deleted_count": n - len(self.docs)})()

    async def insert_one(self, doc):
        self.docs.append(doc)
        return type("R", (), {"inserted_id": "x"})()


class FakeMinio:
    def __init__(self, fail=False):
        self.fail = fail
        self.puts = 0

    def put_object(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("minio down")
        self.puts += 1


def make_article(doc_id="doc-1"):
    return ParsedArticle(url=f"https://x/{doc_id}.htm", title="测试通知", content="内容" * 100,
                         publish_date="2026-08-01", department="教务处", source_site="gzhu",
                         column="通知公告", raw_html="<html>x</html>")


class FakeMinioSdk:
    """按真实 MinIO SDK 契约：data 必须是带 read() 的流对象。"""

    def __init__(self):
        self.objects = {}

    def put_object(self, bucket, name, data, length, **kwargs):
        body = data.read()
        self.objects[name] = (body, length)


@pytest.mark.asyncio
async def test_ingest_minio_receives_stream_and_stores_snapshot():
    """MinIO 正常时：put_object 收到流对象，快照落库且 snapshot_missing=False。"""
    milvus, mongo = FakeMilvus(), FakeMongo()
    minio = FakeMinioSdk()
    doc_id = await ingest_document(make_article(), "通知公告", [], "2026-10-30",
                                   embed_fn=lambda texts: [{"dense": [0.1] * 4, "sparse": {1: 0.5}} for _ in texts],
                                   milvus=milvus, mongo_db=mongo, minio=minio)
    assert mongo.docs[0]["snapshot_missing"] is False
    assert f"snapshots/{doc_id}.html" in minio.objects


@pytest.mark.asyncio
async def test_ingest_reinsert_same_doc_removes_old():
    milvus, mongo = FakeMilvus(), FakeMongo()
    doc_id = await ingest_document(make_article(), "通知公告", [], "2026-10-30",
                                   embed_fn=lambda texts: [{"dense": [0.1] * 4, "sparse": {1: 0.5}} for _ in texts],
                                   milvus=milvus, mongo_db=mongo, minio=FakeMinio())
    # 第二次入库同一 doc：先删后插，不产生重复
    doc_id2 = await ingest_document(make_article(), "通知公告", [], "2026-10-30",
                                    embed_fn=lambda texts: [{"dense": [0.1] * 4, "sparse": {1: 0.5}} for _ in texts],
                                    milvus=milvus, mongo_db=mongo, minio=FakeMinio())
    assert doc_id == doc_id2
    assert len(mongo.docs) == 1
    assert milvus.deleted  # 有先删动作


@pytest.mark.asyncio
async def test_ingest_minio_down_degrades():
    milvus, mongo = FakeMilvus(), FakeMongo()
    doc_id = await ingest_document(make_article(), "通知公告", [], "2026-10-30",
                                   embed_fn=lambda texts: [{"dense": [0.1] * 4, "sparse": {1: 0.5}} for _ in texts],
                                   milvus=milvus, mongo_db=mongo, minio=FakeMinio(fail=True))
    assert len(doc_id) == 16  # doc_id_of = md5(url)[:16]（十六进制 16 位）
    assert len(mongo.docs) == 1
    assert mongo.docs[0]["snapshot_missing"] is True


@pytest.mark.asyncio
async def test_ingest_explicit_doc_id():
    """显式传入 doc_id 时，返回并落库该 doc_id（而非按 url 计算）。"""
    milvus, mongo = FakeMilvus(), FakeMongo()
    doc_id = await ingest_document(make_article(), "通知公告", [], "2026-10-30",
                                   embed_fn=lambda texts: [{"dense": [0.1] * 4, "sparse": {1: 0.5}} for _ in texts],
                                   milvus=milvus, mongo_db=mongo, minio=FakeMinio(),
                                   doc_id="manual-0001")
    assert doc_id == "manual-0001"
    assert mongo.docs[0]["doc_id"] == "manual-0001"
