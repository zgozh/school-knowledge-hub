# 人工数据入库（录入+上传+编辑/删除）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理端新增「人工数据入库」——手动录入或上传文件（PDF/Word/文本）入库、可编辑/删除，复用现有 ingest 管线，落地立即可问答检索。

**Architecture:** 复用 `ingest_document` 三写入库管线作为唯一入库出口，新增薄业务层 `collector/manual.py`（编排 create/update/delete）与纯函数 `collector/parser/file_parser.py`（文件→正文），API 层 `collector/api/manual.py` 暴露 4 个端点；前端在知识库管理页内嵌「新增知识」对话框 + 详情抽屉加编辑/删除。

**Tech Stack:** FastAPI、motor、pymilvus、minio、pypdf、python-docx、Vue 3 + Element Plus、vitest + @vue/test-utils、pytest + httpx。

**Spec:** `docs/superpowers/specs/2026-08-20-manual-data-ingestion-design.md`

## Global Constraints

- 手动文档 `source_site="manual"`，`column` 默认 `"人工录入"`（用户可改）。
- `doc_id = uuid4().hex[:16]`，创建时生成、编辑时复用同一 id。
- `url` 未填时存内部占位 `manual://{doc_id}`（不产生外链）。
- 分类/专题前端可手选；未选走规则：`classify_category(title, column)`、`rule_tag_topics(title, content)`。
- 时效：`infer_expiry(title, content, category, publish_date)`；`publish_date` 空回退今天。
- 文件格式 `.pdf`/`.docx`/`.txt`/`.md`，大小上限 10MB。
- 新依赖 `pypdf` + `python-docx`（仅 collector 需要；model_server/qa_api 不加）。
- 删除清三处：Mongo `delete_many` + Milvus `delete(filter=doc_id==)` + MinIO `remove_object`（MinIO 失败容错）。
- 编辑复用 doc_id 幂等覆盖；url/publish_date/department/column 未填保留原文档值，category/topics 未填走规则重算。

---

### Task 1: `ingest_document` 支持显式 doc_id

**Files:**
- Modify: `collector/ingest/writer.py`（`ingest_document` 签名）
- Test: `tests/test_ingest_idempotent.py`（追加用例）

**Interfaces:**
- Produces: `ingest_document(parsed, category, topics, expire_at, embed_fn=None, milvus=None, mongo_db=None, minio=None, doc_id=None) -> str` —— 显式 `doc_id` 优先，否则沿用 `doc_id_of(parsed.url)`。后续 Task 3 依赖此参数。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_ingest_idempotent.py` 末尾）

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_ingest_idempotent.py::test_ingest_explicit_doc_id -v`
Expected: FAIL（TypeError: unexpected keyword argument 'doc_id'）

- [ ] **Step 3: 最小实现**

`collector/ingest/writer.py`：函数签名在 `minio=None` 后加 `, doc_id: str | None = None`；函数体第 64 行 `doc_id = doc_id_of(parsed.url)` 改为：

```python
    doc_id = doc_id or doc_id_of(parsed.url)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_ingest_idempotent.py -v`
Expected: PASS（4 个用例全过）

- [ ] **Step 5: Commit**

```bash
git add collector/ingest/writer.py tests/test_ingest_idempotent.py
git commit -m "feat: ingest_document支持显式doc_id(人工入库稳定id复用)"
```

---

### Task 2: 文件解析 `file_parser.py`

**Files:**
- Create: `collector/parser/file_parser.py`
- Test: `tests/test_file_parser.py`
- Modify: `pyproject.toml`（加依赖）

**Interfaces:**
- Produces: `parse_file(filename: str, data: bytes) -> dict`，返回 `{"title": str, "content": str}`；不支持格式/空内容抛 `ValueError`。内部 `_extract_pdf(data)`、`_extract_docx(data)`、`_decode_text(data)`。Task 4 的 parse-file 端点依赖此函数。

- [ ] **Step 1: 装依赖**

Run: `uv add pypdf python-docx`
Expected: 依赖加入 `pyproject.toml` + lockfile。

- [ ] **Step 2: 写失败测试**（`tests/test_file_parser.py`）

```python
import pytest

from collector.parser import file_parser


def test_parse_txt_returns_title_and_content():
    result = file_parser.parse_file("通知.txt", "这是正文".encode("utf-8"))
    assert result["title"] == "通知"
    assert result["content"] == "这是正文"


def test_parse_md_decodes_gbk_fallback():
    result = file_parser.parse_file("制度.md", "规章制度内容".encode("gbk"))
    assert "规章制度内容" in result["content"]


def test_parse_unsupported_ext_raises():
    with pytest.raises(ValueError):
        file_parser.parse_file("a.xlsx", b"xx")


def test_parse_empty_content_raises():
    with pytest.raises(ValueError):
        file_parser.parse_file("a.txt", b"   ")


def test_parse_pdf_dispatches(monkeypatch):
    monkeypatch.setattr(file_parser, "_extract_pdf", lambda data: "PDF 正文")
    result = file_parser.parse_file("报告.pdf", b"%PDF-x")
    assert result["content"] == "PDF 正文"


def test_parse_docx_roundtrip(tmp_path):
    from docx import Document
    doc = Document()
    doc.add_paragraph("这是 Word 正文")
    p = tmp_path / "t.docx"
    doc.save(str(p))
    result = file_parser.parse_file("t.docx", p.read_bytes())
    assert "这是 Word 正文" in result["content"]
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_file_parser.py -v`
Expected: FAIL（ModuleNotFoundError: collector.parser.file_parser）

- [ ] **Step 4: 最小实现**（`collector/parser/file_parser.py`）

```python
"""文件解析：PDF/Word/纯文本/Markdown → {title, content}。"""
from pathlib import Path


def parse_file(filename: str, data: bytes) -> dict:
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md"):
        content = _decode_text(data)
    elif ext == ".pdf":
        content = _extract_pdf(data)
    elif ext == ".docx":
        content = _extract_docx(data)
    else:
        raise ValueError(f"不支持的文件类型: {ext or '(无扩展名)'}")
    if not content.strip():
        raise ValueError("文件解析结果为空")
    return {"title": Path(filename).stem, "content": content}


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gbk")


def _extract_pdf(data: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_file_parser.py -v`
Expected: PASS（6 个用例全过）

- [ ] **Step 6: Commit**

```bash
git add collector/parser/file_parser.py tests/test_file_parser.py pyproject.toml uv.lock
git commit -m "feat: 文件解析file_parser(PDF/Word/纯文本/Markdown→标题正文)"
```

---

### Task 3: 业务编排 `collector/manual.py`

**Files:**
- Create: `collector/manual.py`
- Test: `tests/test_manual.py`

**Interfaces:**
- Consumes: `ingest_document(..., doc_id=...)`（Task 1）、`classify_category`/`rule_tag_topics`（已有）、`infer_expiry`（已有）、`ParsedArticle`（已有）。
- Produces:
  - `create_document(payload: dict, mongo_db=None, milvus=None, minio=None, ingest_fn=None) -> str`
  - `update_document(doc_id: str, payload: dict, mongo_db=None, milvus=None, minio=None, ingest_fn=None) -> str | None`
  - `delete_document(doc_id: str, mongo_db=None, milvus=None, minio=None) -> bool`
  - Task 4 的端点依赖这三个函数。

- [ ] **Step 1: 写失败测试**（`tests/test_manual.py`）

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_manual.py -v`
Expected: FAIL（ModuleNotFoundError: collector.manual）

- [ ] **Step 3: 最小实现**（`collector/manual.py`）

```python
"""人工数据入库：录入/上传/编辑/删除的业务编排（复用 ingest_document 管线）。"""
import uuid
from datetime import datetime

from collector.ingest.writer import ingest_document
from collector.lifecycle.validity import infer_expiry
from collector.parser.extract import ParsedArticle
from collector.tagger.rules import classify_category, rule_tag_topics
from shared.clients import get_milvus, get_minio, get_mongo
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("collector.manual")


async def create_document(payload: dict, mongo_db=None, milvus=None, minio=None, ingest_fn=None) -> str:
    doc_id = uuid.uuid4().hex[:16]
    url = payload.get("url") or f"manual://{doc_id}"
    await _ingest(doc_id, url, payload, mongo_db=mongo_db, milvus=milvus, minio=minio, ingest_fn=ingest_fn)
    return doc_id


async def update_document(doc_id: str, payload: dict, mongo_db=None, milvus=None, minio=None, ingest_fn=None) -> str | None:
    db = mongo_db or get_mongo()
    existing = await db["documents"].find_one({"doc_id": doc_id})
    if existing is None:
        return None
    url = payload.get("url") or existing.get("url") or f"manual://{doc_id}"
    merged = dict(payload)
    merged.setdefault("publish_date", existing.get("publish_date"))
    merged.setdefault("department", existing.get("department"))
    merged.setdefault("column", existing.get("column"))
    await _ingest(doc_id, url, merged, mongo_db=mongo_db, milvus=milvus, minio=minio, ingest_fn=ingest_fn)
    return doc_id


async def delete_document(doc_id: str, mongo_db=None, milvus=None, minio=None) -> bool:
    db = mongo_db or get_mongo()
    await db["documents"].delete_many({"doc_id": doc_id})
    (milvus or get_milvus()).delete(settings.milvus_collection, filter=f'doc_id == "{doc_id}"')
    try:
        (minio or get_minio()).remove_object(settings.minio_bucket, f"snapshots/{doc_id}.html")
    except Exception as e:
        logger.warning("删除 MinIO 快照失败(容错): %s", e)
    return True


async def _ingest(doc_id: str, url: str, payload: dict, mongo_db=None, milvus=None, minio=None, ingest_fn=None) -> None:
    title = payload["title"]
    content = payload["content"]
    column = payload.get("column") or "人工录入"
    category = payload.get("category") or classify_category(title, column)
    topics = payload.get("topics") or rule_tag_topics(title, content)
    publish_date = payload.get("publish_date") or datetime.now().strftime("%Y-%m-%d")
    expire_at = infer_expiry(title, content, category, publish_date)
    parsed = ParsedArticle(
        url=url, title=title, content=content, publish_date=publish_date,
        department=payload.get("department"), source_site="manual", column=column,
        raw_html=f"<html><head><title>{title}</title></head><body><h1>{title}</h1><p>{content}</p></body></html>",
    )
    await (ingest_fn or ingest_document)(parsed, category, topics, expire_at,
                                         mongo_db=mongo_db, milvus=milvus, minio=minio, doc_id=doc_id)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_manual.py -v`
Expected: PASS（6 个用例全过）

- [ ] **Step 5: Commit**

```bash
git add collector/manual.py tests/test_manual.py
git commit -m "feat: 人工入库业务编排(create/update复用doc_id幂等覆盖/delete清三处)"
```

---

### Task 4: 人工入库 API 端点 + 路由注册 + 容器依赖

**Files:**
- Create: `collector/api/manual.py`
- Modify: `collector/main.py`（注册 router）
- Modify: `collector/Dockerfile`（加 pypdf python-docx）
- Test: `tests/test_manual_api.py`

**Interfaces:**
- Consumes: `manual.create_document/update_document/delete_document`（Task 3）、`file_parser.parse_file`（Task 2）。
- Produces: HTTP 端点（前缀 `/api/admin/manual`）：`POST /parse-file`、`POST /documents`、`PUT /documents/{doc_id}`、`DELETE /documents/{doc_id}`。前端 Task 5 依赖这些端点。

- [ ] **Step 1: 写失败测试**（`tests/test_manual_api.py`）

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_manual_api.py -v`
Expected: FAIL（404 Not Found，路由未注册）

- [ ] **Step 3: 最小实现**

`collector/api/manual.py`：

```python
"""人工数据入库 API（录入/上传/编辑/删除）。"""
from fastapi import APIRouter, HTTPException, UploadFile

from collector import manual

router = APIRouter(prefix="/api/admin/manual", tags=["人工入库"])

MAX_FILE_BYTES = 10 * 1024 * 1024


@router.post("/parse-file")
async def parse_file(file: UploadFile):
    from collector.parser.file_parser import parse_file as do_parse

    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="文件过大（上限 10MB）")
    try:
        return do_parse(file.filename or "未命名.txt", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents")
async def create_document(payload: dict):
    if not (payload.get("title") and payload.get("content")):
        raise HTTPException(status_code=400, detail="标题与正文必填")
    return {"doc_id": await manual.create_document(payload)}


@router.put("/documents/{doc_id}")
async def update_document(doc_id: str, payload: dict):
    if not (payload.get("title") and payload.get("content")):
        raise HTTPException(status_code=400, detail="标题与正文必填")
    result = await manual.update_document(doc_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"doc_id": result}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    await manual.delete_document(doc_id)
    return {"deleted": True}
```

`collector/main.py`：在 import 区加 `from collector.api import manual as manual_api`，在三个 `include_router` 后加 `app.include_router(manual_api.router)`。

`collector/Dockerfile`：pip 安装列表末尾加 ` pypdf python-docx`。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_manual_api.py -v`
Expected: PASS（5 个用例全过）

- [ ] **Step 5: Commit**

```bash
git add collector/api/manual.py collector/main.py collector/Dockerfile tests/test_manual_api.py
git commit -m "feat: 人工入库API(parse-file/documents增删改)+路由注册+容器依赖"
```

---

### Task 5: 前端人工入库表单 + 编辑/删除交互

**Files:**
- Modify: `frontend/src/api/request.js`（支持 FormData）
- Modify: `frontend/src/api/admin.js`（加 manualApi 方法）
- Modify: `frontend/src/composables/useKnowledge.js`（加 create/update/remove）
- Modify: `frontend/src/views/admin/KnowledgeView.vue`（新增表单对话框 + 详情抽屉编辑/删除）
- Test: `frontend/tests/manualForm.test.js`

**Interfaces:**
- Consumes: HTTP 端点 `/api/admin/manual/*`（Task 4）。
- Produces: `adminApi.parseFile/createDocument/updateDocument/removeDocument`；`useKnowledge().create/update/remove`。

- [ ] **Step 1: 写失败测试**（`frontend/tests/manualForm.test.js`）

```js
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const mocks = vi.hoisted(() => ({
  listKnowledge: vi.fn(),
  getKnowledgeDetail: vi.fn(),
  setDocStatus: vi.fn(),
  expiryCheck: vi.fn(),
  createDocument: vi.fn(),
  updateDocument: vi.fn(),
  removeDocument: vi.fn(),
  parseFile: vi.fn(),
}))

vi.mock('../src/api/admin', () => ({ adminApi: mocks }))

import KnowledgeView from '../src/views/admin/KnowledgeView.vue'

function mountView() {
  return mount(KnowledgeView, { global: { plugins: [ElementPlus] } })
}

describe('KnowledgeView 人工数据入库', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listKnowledge.mockResolvedValue({ items: [], total: 0 })
    mocks.createDocument.mockResolvedValue({ doc_id: 'm1' })
    mocks.getKnowledgeDetail.mockResolvedValue({ doc_id: 'm1', url: 'manual://m1', title: 't', content: 'c', topics: [], status: 'active' })
  })

  it('页头有「新增知识」按钮，点击打开表单', async () => {
    const wrapper = mountView()
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text().includes('新增知识'))
    expect(btn).toBeTruthy()
    await btn.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('标题')
  })

  it('填表提交调用 createDocument', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text().includes('新增知识')).trigger('click')
    await flushPromises()
    await wrapper.find('input').setValue('标题X')
    await wrapper.find('textarea').setValue('正文Y')
    await wrapper.findAll('button').find((b) => b.text().includes('保存')).trigger('click')
    await flushPromises()
    expect(mocks.createDocument).toHaveBeenCalled()
    const payload = mocks.createDocument.mock.calls[0][0]
    expect(payload.title).toBe('标题X')
    expect(payload.content).toBe('正文Y')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && pnpm exec vitest run tests/manualForm.test.js`
Expected: FAIL（「新增知识」按钮不存在 / createDocument 未定义）

- [ ] **Step 3: 最小实现**

`frontend/src/api/request.js` 改为支持 FormData：

```js
/** fetch JSON 封装：非 2xx 抛出中文错误；isForm=true 时按 multipart 发送。 */
export async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const resp = await fetch(path, {
    method,
    headers: body && !isForm ? { 'Content-Type': 'application/json' } : undefined,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) {
    let msg = `请求失败（HTTP ${resp.status}）`
    try {
      const data = await resp.json()
      if (data?.detail) msg = typeof data.detail === 'string' ? data.detail : msg
      if (data?.error) msg = typeof data.error === 'string' ? data.error : msg
    } catch { /* 忽略非 JSON 错误体 */ }
    throw new Error(msg)
  }
  return resp.json()
}
```

`frontend/src/api/admin.js` 末尾加：

```js
  // 人工数据入库
  parseFile: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('/admin-api/api/admin/manual/parse-file', { method: 'POST', body: fd, isForm: true })
  },
  createDocument: (payload) => request('/admin-api/api/admin/manual/documents', { method: 'POST', body: payload }),
  updateDocument: (docId, payload) => request(`/admin-api/api/admin/manual/documents/${docId}`, { method: 'PUT', body: payload }),
  removeDocument: (docId) => request(`/admin-api/api/admin/manual/documents/${docId}`, { method: 'DELETE' }),
```

`frontend/src/composables/useKnowledge.js`：解构处加 `create/update/remove`，return 加对应方法：

```js
  async function create(payload) { return adminApi.createDocument(payload) }
  async function update(docId, payload) { return adminApi.updateDocument(docId, payload) }
  async function remove(docId) { return adminApi.removeDocument(docId) }

  return { items, total, loading, error, load, setStatus, expiryCheck, getDetail, create, update, remove }
```

`frontend/src/views/admin/KnowledgeView.vue`：
- 页头按钮区（「到期检测」旁）加：

```html
<el-button type="primary" @click="openCreate">新增知识</el-button>
```

- 详情抽屉 `.detail-actions` 内加编辑/删除（在「打开原文」按钮后）：

```html
<el-button type="primary" plain @click="openEditFromDetail()">编辑</el-button>
<el-popconfirm title="确认删除该文档？" @confirm="onRemoveFromDetail()">
  <template #reference><el-button type="danger" plain>删除</el-button></template>
</el-popconfirm>
```

- `</el-drawer>` 之后、`</section>` 之前加表单对话框：

```html
<el-dialog v-model="formVisible" :title="formMode === 'create' ? '新增知识' : '编辑知识'" width="640px">
  <el-form :model="form" label-width="90px">
    <el-form-item v-if="formMode === 'create'" label="正文来源">
      <el-radio-group v-model="sourceType">
        <el-radio value="manual">手动录入</el-radio>
        <el-radio value="upload">上传文件</el-radio>
      </el-radio-group>
    </el-form-item>
    <el-form-item v-if="formMode === 'create' && sourceType === 'upload'" label="文件">
      <el-upload :auto-upload="false" :limit="1" accept=".pdf,.docx,.txt,.md" :on-change="onFileChange">
        <el-button type="primary" plain>选择文件</el-button>
      </el-upload>
    </el-form-item>
    <el-form-item label="标题" required>
      <el-input v-model="form.title" placeholder="文档标题" />
    </el-form-item>
    <el-form-item label="正文" required>
      <el-input v-model="form.content" type="textarea" :rows="8" placeholder="正文内容（可粘贴）" />
    </el-form-item>
    <el-form-item label="发布日期">
      <el-date-picker v-model="form.publish_date" type="date" value-format="YYYY-MM-DD" placeholder="默认今天" />
    </el-form-item>
    <el-form-item label="分类">
      <el-select v-model="form.category" clearable placeholder="未选则自动">
        <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
      </el-select>
    </el-form-item>
    <el-form-item label="专题域">
      <el-select v-model="form.topics" multiple clearable placeholder="未选则自动">
        <el-option v-for="t in TOPICS" :key="t" :label="t" :value="t" />
      </el-select>
    </el-form-item>
    <el-form-item label="来源 URL">
      <el-input v-model="form.url" placeholder="可选" />
    </el-form-item>
    <el-form-item label="发布部门">
      <el-input v-model="form.department" placeholder="可选" />
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="formVisible = false">取消</el-button>
    <el-button type="primary" :loading="saving" @click="onSubmit">保存</el-button>
  </template>
</el-dialog>
```

- script 中：`useKnowledge` 解构加 `create, update, remove`；加状态与方法：

```js
const formVisible = ref(false)
const formMode = ref('create')
const sourceType = ref('manual')
const saving = ref(false)
const editingDocId = ref(null)
const form = reactive({ title: '', content: '', publish_date: '', category: '', topics: [], url: '', department: '' })

function openCreate() {
  formMode.value = 'create'
  sourceType.value = 'manual'
  editingDocId.value = null
  Object.assign(form, { title: '', content: '', publish_date: '', category: '', topics: [], url: '', department: '' })
  formVisible.value = true
}
async function openEditFromDetail() {
  formMode.value = 'edit'
  editingDocId.value = detail.value.doc_id
  Object.assign(form, {
    title: detail.value.title || '', content: detail.value.content || '',
    publish_date: detail.value.publish_date || '', category: detail.value.category || '',
    topics: detail.value.topics || [], url: detail.value.url || '', department: detail.value.department || '',
  })
  formVisible.value = true
}
async function onFileChange(file) {
  try {
    const res = await parseFile(file.raw)
    form.title = res.title
    form.content = res.content
  } catch (e) { ElMessage.error(e.message) }
}
async function onSubmit() {
  if (!form.title.trim() || !form.content.trim()) { ElMessage.warning('标题与正文必填'); return }
  saving.value = true
  try {
    const payload = { title: form.title.trim(), content: form.content,
      publish_date: form.publish_date || undefined, category: form.category || undefined,
      topics: form.topics.length ? form.topics : undefined, url: form.url || undefined,
      department: form.department || undefined }
    if (formMode.value === 'create') await create(payload)
    else await update(editingDocId.value, payload)
    ElMessage.success('已保存')
    formVisible.value = false
    await loadPage()
  } catch (e) { ElMessage.error(e.message) } finally { saving.value = false }
}
async function onRemoveFromDetail() {
  try {
    await remove(detail.value.doc_id)
    ElMessage.success('已删除')
    detailVisible.value = false
    await loadPage()
  } catch (e) { ElMessage.error(e.message) }
}
```

- script 顶部 import 加 `parseFile`（从 adminApi）——通过 useKnowledge 解构处统一引入：`const { ..., create, update, remove, getDetail } = useKnowledge()`，另从 `../../api/admin` 引入 `adminApi` 用于 parseFile。最简：在 useKnowledge 也暴露 `parseFile`，或组件里 `import { adminApi } from '../../api/admin'` 后 `adminApi.parseFile`。采用后者：

```js
import { adminApi } from '../../api/admin'
```

`onFileChange` 里改 `const res = await adminApi.parseFile(file.raw)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && pnpm exec vitest run tests/manualForm.test.js`
Expected: PASS（2 个用例全过）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/request.js frontend/src/api/admin.js frontend/src/composables/useKnowledge.js frontend/src/views/admin/KnowledgeView.vue frontend/tests/manualForm.test.js
git commit -m "feat: 前端人工入库表单(录入/上传回填/编辑/删除)+request支持FormData"
```

---

## Self-Review

**1. Spec coverage：**
- 录入表单 → Task 5（表单 + createDocument）✅
- 上传文件解析 → Task 2（file_parser）+ Task 4（parse-file 端点）+ Task 5（上传回填）✅
- 编辑 → Task 3（update_document 幂等覆盖）+ Task 5（编辑回填）✅
- 删除 → Task 3（delete_document 清三处）+ Task 5（删除交互）✅
- 数据模型标识（source_site=manual / doc_id 稳定 / manual:// 占位）→ Task 1 + Task 3 ✅
- 依赖 pypdf/python-docx → Task 2 + Task 4 ✅
- 错误处理（解析失败/空内容/10MB）→ Task 2 + Task 4 ✅

**2. Placeholder scan：** 无 TBD/TODO，所有代码块完整。

**3. Type consistency：**
- `ingest_document(..., doc_id=...)`：Task 1 定义，Task 3 调用一致 ✅
- `parse_file(filename, data) -> dict{title,content}`：Task 2 定义，Task 4 端点调用一致 ✅
- `manual.create_document/update_document/delete_document`：Task 3 定义，Task 4 端点一致 ✅
- 前端 `adminApi.parseFile/createDocument/updateDocument/removeDocument`：Task 5 定义并调用一致 ✅
- `useKnowledge().create/update/remove/getDetail`：Task 5 定义并调用一致 ✅

---

## Execution Handoff

计划完成，共 5 个任务（后端 4 + 前端 1），每个任务 TDD 五步 + 独立 commit。

**执行方式选择：**
1. **Subagent-Driven（推荐）**：每任务派一个新鲜子代理 + 两步评审（按 AGENTS.md 模型分工：后端 glm-5.3、前端 kimi-k3）。
2. **Inline（本会话直接执行）**：主会话逐任务 TDD 实现，需真跑验证（模型服务在线、文件解析依赖安装、前端 build）。

鉴于本计划 5 个任务前后强依赖（ingest→file_parser→manual→API→前端）、且需要真跑验证（embedding/文件解析/前端 build），建议 **Inline 执行**（同前几批主会话接管经验，子代理曾空转）。
