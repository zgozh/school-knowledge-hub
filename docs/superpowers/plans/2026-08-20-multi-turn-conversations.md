# 多轮会话 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给问答端加「多轮会话 + 历史会话持久化 + 侧边栏」，对标豆包式会话管理（新建/切换/删除，刷新不丢）。

**Architecture:** 方案 A 后端权威——会话落 MongoDB `conversations` 集合（单集合内嵌 messages），`/chat` 契约从「前端传 history」改为「前端传 conversation_id，后端读会话拼历史」。前端 ChatView 改两栏（Sidebar + 主对话区），状态用 composable 收敛（不引 Pinia）。

**Tech Stack:** FastAPI + motor(MongoDB) + pytest / Vue3 + Element Plus + vitest。

**Spec:** `docs/superpowers/specs/2026-08-20-multi-turn-conversations-design.md`

## Global Constraints

- motor 异步：**所有 Mongo 调用必须 `await`**；`get_mongo()` 返回 `school_knowledge_hub` 库。
- `conversation_id = uuid4().hex[:16]`；`title = query[:20]`（超长加 `…`），仅建会话时写一次。
- 上下文窗口：沿用 `llm.py` 已有 `history[-6:]`（最近 6 条消息），**不改生成层**。
- 会话落库失败不阻断答案流（try/except 降级，done 仍返回、conversation_id 为 null）。
- 无鉴权/多用户、无重命名、无 URL 深链、不引 Pinia（spec §8 范围外，一律不做）。
- TDD：先写失败测试 → 看失败 → 最小实现 → 看通过 → commit（每任务一个 commit）。
- 后端测试命令：`uv run pytest tests/<file>.py -v`（本计划各任务测试均为纯 mock，无需 `DEEPSEEK_API_KEY`）；全量回归（Task 8）需注入 `$env:DEEPSEEK_API_KEY=[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')`。
- 前端测试命令：在 `frontend/` 目录跑 `pnpm exec vitest run tests/<file>.test.js`。

---

### Task 1: 会话业务函数 `qa_api/conversations.py`

**Files:**
- Create: `qa_api/conversations.py`
- Test: `tests/test_conversations.py`

**Interfaces:**
- Consumes: `get_mongo()` 返回的 `AsyncIOMotorDatabase`（由调用方传入，函数不自己取，便于测试注入）。
- Produces:
  - `async def list_conversations(db) -> list[dict]` → `[{conversation_id, title, updated_at, message_count}]`（不含 messages 全量）
  - `async def get_conversation(db, conversation_id: str) -> dict | None`
  - `async def delete_conversation(db, conversation_id: str) -> bool`
  - `async def append_or_create(db, conversation_id: str | None, query: str, answer: str, sources: list) -> str` → 返回最终 conversation_id

- [ ] **Step 1: 写失败测试** `tests/test_conversations.py`

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_conversations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qa_api.conversations'`

- [ ] **Step 3: 写最小实现** `qa_api/conversations.py`

```python
"""会话存储/查询业务函数（依赖注入 db，供 API 与 /chat 共用）。"""
import time
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


async def list_conversations(db) -> list[dict]:
    docs = await db["conversations"].find({}).sort("updated_at", -1).to_list(None)
    return [
        {
            "conversation_id": d["conversation_id"],
            "title": d.get("title", ""),
            "updated_at": d.get("updated_at", ""),
            "message_count": len(d.get("messages", [])),
        }
        for d in docs
    ]


async def get_conversation(db, conversation_id: str) -> dict | None:
    return await db["conversations"].find_one({"conversation_id": conversation_id})


async def delete_conversation(db, conversation_id: str) -> bool:
    await db["conversations"].delete_many({"conversation_id": conversation_id})
    return True


async def append_or_create(db, conversation_id: str | None, query: str, answer: str, sources: list) -> str:
    now = _now()
    user_msg = {"role": "user", "content": query, "created_at": now}
    assistant_msg = {"role": "assistant", "content": answer, "sources": sources, "created_at": now}
    if conversation_id:
        existing = await db["conversations"].find_one({"conversation_id": conversation_id})
        if existing:
            await db["conversations"].update_one(
                {"conversation_id": conversation_id},
                {"$push": {"messages": {"$each": [user_msg, assistant_msg]}},
                 "$set": {"updated_at": now}},
            )
            return conversation_id
    new_id = uuid.uuid4().hex[:16]
    await db["conversations"].insert_one({
        "conversation_id": new_id,
        "title": query[:20] + ("…" if len(query) > 20 else ""),
        "messages": [user_msg, assistant_msg],
        "created_at": now,
        "updated_at": now,
    })
    return new_id
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_conversations.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add qa_api/conversations.py tests/test_conversations.py
git commit -m "feat: 会话业务函数(list/get/delete/append_or_create,依赖注入db)"
```

---

### Task 2: 会话 API 路由 `qa_api/api/conversations.py`

**Files:**
- Create: `qa_api/api/conversations.py`
- Modify: `qa_api/main.py`（注册 router）
- Test: `tests/test_conversations_api.py`

**Interfaces:**
- Consumes: Task 1 的 `qa_api.conversations.{list_conversations, get_conversation, delete_conversation}`。
- Produces: router（`/api/conversations` GET 列表 / GET 详情 / DELETE 删除），供 main.py `include_router`。

- [ ] **Step 1: 写失败测试** `tests/test_conversations_api.py`

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_conversations_api.py -v`
Expected: FAIL — 路由 404（`qa_api.api.conversations` 模块不存在 / 未注册）

- [ ] **Step 3: 写最小实现**

`qa_api/api/conversations.py`：

```python
"""会话管理 API：列表/详情/删除。"""
from fastapi import APIRouter, HTTPException

from qa_api.conversations import (
    delete_conversation as _delete,
    get_conversation as _get,
    list_conversations as _list,
)
from shared.clients import get_mongo

router = APIRouter(prefix="/api/conversations", tags=["会话"])


@router.get("")
async def list_endpoint():
    return await _list(get_mongo())


@router.get("/{conversation_id}")
async def get_endpoint(conversation_id: str):
    conv = await _get(get_mongo(), conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


@router.delete("/{conversation_id}")
async def delete_endpoint(conversation_id: str):
    await _delete(get_mongo(), conversation_id)
    return {"deleted": True}
```

`qa_api/main.py` 顶部加 import、底部注册：

```python
from qa_api.api import chat, conversations
...
app.include_router(chat.router)
app.include_router(conversations.router)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_conversations_api.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add qa_api/api/conversations.py qa_api/main.py tests/test_conversations_api.py
git commit -m "feat: 会话API(列表/详情/删除)+main注册"
```

---

### Task 3: `/chat` 改造（conversation_id 契约 + 落库）

**Files:**
- Modify: `qa_api/api/chat.py`
- Test: `tests/test_chat_conversation.py`

**Interfaces:**
- Consumes: Task 1 的 `qa_api.conversations.{get_conversation, append_or_create}`；现有 `hybrid_search / rerank_chunks / cliff_cutoff / stream_answer / build_context / get_mongo`。
- Produces: `POST /api/chat` 契约 `{query, topic?, conversation_id?}`；`done` 事件 data 新增 `conversation_id` 字段（新建时返回新 id，失败为 null）。

- [ ] **Step 1: 写失败测试** `tests/test_chat_conversation.py`

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_chat_conversation.py -v`
Expected: FAIL — `done` 事件无 `conversation_id`（`assert done and done["conversation_id"]` 失败）

- [ ] **Step 3: 写最小实现**（改 `qa_api/api/chat.py`）

顶部 import 加：

```python
from qa_api.conversations import append_or_create, get_conversation
```

`ChatRequest` 改为：

```python
class ChatRequest(BaseModel):
    query: str
    topic: str | None = None
    conversation_id: str | None = None
```

`event_stream` 内，在检索后、生成前拼 history；生成后、sources 后落库；done 带 id：

```python
async def event_stream():
    try:
        chunks = await hybrid_search(req.query, topics=[req.topic] if req.topic else None)
        if not chunks:
            yield {"event": "empty", "data": json.dumps({"message": EMPTY_MESSAGE}, ensure_ascii=False)}
            return
        chunks = rerank_chunks(req.query, chunks)
        chunks = cliff_cutoff(chunks)
        answer_parts: list[str] = []

        history = None
        if req.conversation_id:
            conv = await get_conversation(get_mongo(), req.conversation_id)
            if conv:
                history = [{"role": m["role"], "content": m["content"]}
                           for m in conv.get("messages", [])]

        async def generate():
            async for delta in stream_answer(req.query, build_context(chunks), history):
                answer_parts.append(delta)
                yield {"event": "chunk", "data": json.dumps({"delta": delta}, ensure_ascii=False)}

        async for ev in generate():
            yield ev

        sources = []
        for c in chunks:
            doc = await get_mongo()["documents"].find_one({"doc_id": c.doc_id})
            sources.append({
                "doc_id": c.doc_id,
                "title": (doc or {}).get("title", ""),
                "url": (doc or {}).get("url", ""),
                "publish_date": c.publish_date,
                "category": c.category,
                "expired": c.expired,
            })
        yield {"event": "sources", "data": json.dumps({"sources": sources}, ensure_ascii=False)}
        answer = "".join(answer_parts)

        conv_id = None
        try:
            conv_id = await append_or_create(get_mongo(), req.conversation_id, req.query, answer, sources)
        except Exception as e:
            logger.warning("会话落库失败(降级): %s", e)

        elapsed_ms = int((time.monotonic() - started) * 1000)
        try:
            await get_mongo()["qa_logs"].insert_one({
                "query_id": query_id, "query": req.query, "answer": answer,
                "sources": [s["url"] for s in sources], "elapsed_ms": elapsed_ms,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception as e:
            logger.warning("问答日志写入失败(降级): %s", e)
        yield {"event": "done",
               "data": json.dumps({"query_id": query_id, "elapsed_ms": elapsed_ms,
                                   "answer_len": len(answer), "conversation_id": conv_id},
                                  ensure_ascii=False)}
    except ExternalServiceError as e:
        yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_chat_conversation.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add qa_api/api/chat.py tests/test_chat_conversation.py
git commit -m "feat: /chat改conversation_id契约+会话落库(done返回id,失败降级)"
```

---

### Task 4: 前端 API 层 `api/chat.js` 扩展

**Files:**
- Modify: `frontend/src/api/chat.js`
- Test: `frontend/tests/chatApi.test.js`

**Interfaces:**
- Consumes: `request()`（`frontend/src/api/request.js`）、`sseFetch()`（`frontend/src/api/sseFetch.js`）。
- Produces:
  - `listConversations() -> Promise<array>`
  - `getConversation(id) -> Promise<object>`
  - `deleteConversation(id) -> Promise<object>`
  - `askChat(query, topic, conversationId, callbacks)`（第 3 参从 history 改为 conversationId；body 传 `conversation_id: conversationId ?? null`）

- [ ] **Step 1: 写失败测试** `frontend/tests/chatApi.test.js`

```js
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { listConversations, getConversation, deleteConversation } from '../src/api/chat'

describe('会话 API 层', () => {
  beforeEach(() => { global.fetch = vi.fn() })
  afterEach(() => { vi.restoreAllMocks() })

  it('listConversations 调 GET /qa-api/api/conversations', async () => {
    global.fetch.mockResolvedValue({ ok: true, json: async () => [{ conversation_id: 'c1' }] })
    const out = await listConversations()
    expect(out[0].conversation_id).toBe('c1')
    expect(global.fetch).toHaveBeenCalledWith('/qa-api/api/conversations',
      expect.objectContaining({ method: 'GET' }))
  })

  it('getConversation 调 GET 详情', async () => {
    global.fetch.mockResolvedValue({ ok: true, json: async () => ({ conversation_id: 'c1', messages: [] }) })
    await getConversation('c1')
    expect(global.fetch).toHaveBeenCalledWith('/qa-api/api/conversations/c1', expect.any(Object))
  })

  it('deleteConversation 调 DELETE', async () => {
    global.fetch.mockResolvedValue({ ok: true, json: async () => ({ deleted: true }) })
    await deleteConversation('c1')
    expect(global.fetch).toHaveBeenCalledWith('/qa-api/api/conversations/c1',
      expect.objectContaining({ method: 'DELETE' }))
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run（`frontend/` 目录）: `pnpm exec vitest run tests/chatApi.test.js`
Expected: FAIL — `listConversations is not a function`（未导出）

- [ ] **Step 3: 写最小实现** `frontend/src/api/chat.js`

```js
/** 问答端 API（qa_api 服务，经 vite proxy 同源转发）。 */
import { request } from './request'
import { sseFetch } from './sseFetch'

/** 发起一次问答（SSE 流式）。callbacks 见 sseFetch。 */
export function askChat(query, topic, conversationId, callbacks) {
  return sseFetch('/qa-api/api/chat',
    { query, topic, conversation_id: conversationId ?? null }, callbacks)
}

/** 会话列表。 */
export function listConversations() {
  return request('/qa-api/api/conversations')
}

/** 会话详情（含 messages 全量）。 */
export function getConversation(id) {
  return request(`/qa-api/api/conversations/${id}`)
}

/** 删除会话。 */
export function deleteConversation(id) {
  return request(`/qa-api/api/conversations/${id}`, { method: 'DELETE' })
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm exec vitest run tests/chatApi.test.js`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/chat.js frontend/tests/chatApi.test.js
git commit -m "feat: 前端会话API(list/get/delete)+askChat改conversationId"
```

---

### Task 5: 前端会话状态 `composables/useConversations.js`

**Files:**
- Create: `frontend/src/composables/useConversations.js`
- Test: `frontend/tests/useConversations.test.js`

**Interfaces:**
- Consumes: Task 4 的 `listConversations / getConversation / deleteConversation`。
- Produces: `useConversations()` → `{ list, currentId, messages, loading, loadList, newConversation, openConversation, removeConversation }`（均为 `ref` 或方法）。

- [ ] **Step 1: 写失败测试** `frontend/tests/useConversations.test.js`

```js
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useConversations } from '../src/composables/useConversations'
import * as chatApi from '../src/api/chat'

vi.mock('../src/api/chat', () => ({
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
}))

describe('useConversations', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('loadList 拉列表', async () => {
    chatApi.listConversations.mockResolvedValue([{ conversation_id: 'c1', title: 't' }])
    const c = useConversations()
    await c.loadList()
    expect(c.list.value[0].conversation_id).toBe('c1')
  })

  it('newConversation 清空当前会话', async () => {
    const c = useConversations()
    c.currentId.value = 'c1'
    c.messages.value = [{ role: 'user', content: 'x' }]
    c.newConversation()
    expect(c.currentId.value).toBe(null)
    expect(c.messages.value).toEqual([])
  })

  it('openConversation 加载历史 messages', async () => {
    chatApi.getConversation.mockResolvedValue({
      conversation_id: 'c1', messages: [{ role: 'user', content: 'x' }],
    })
    const c = useConversations()
    await c.openConversation('c1')
    expect(c.currentId.value).toBe('c1')
    expect(c.messages.value[0].role).toBe('user')
    expect(c.loading.value).toBe(false)
  })

  it('removeConversation 删除后刷新列表', async () => {
    chatApi.deleteConversation.mockResolvedValue({ deleted: true })
    chatApi.listConversations.mockResolvedValue([])
    const c = useConversations()
    await c.removeConversation('c1')
    expect(chatApi.deleteConversation).toHaveBeenCalledWith('c1')
    expect(c.list.value).toEqual([])
  })

  it('removeConversation 删当前会话则回新会话态', async () => {
    chatApi.deleteConversation.mockResolvedValue({ deleted: true })
    chatApi.listConversations.mockResolvedValue([])
    const c = useConversations()
    c.currentId.value = 'c1'
    c.messages.value = [{ role: 'user', content: 'x' }]
    await c.removeConversation('c1')
    expect(c.currentId.value).toBe(null)
    expect(c.messages.value).toEqual([])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm exec vitest run tests/useConversations.test.js`
Expected: FAIL — `Failed to resolve import '../src/composables/useConversations'`

- [ ] **Step 3: 写最小实现** `frontend/src/composables/useConversations.js`

```js
/** 会话状态：列表 / 当前会话 / 新建 / 切换 / 删除 / 加载。 */
import { ref } from 'vue'
import { listConversations, getConversation, deleteConversation } from '../api/chat'

export function useConversations() {
  const list = ref([])
  const currentId = ref(null)
  const messages = ref([])
  const loading = ref(false)

  async function loadList() {
    list.value = await listConversations()
  }

  function newConversation() {
    currentId.value = null
    messages.value = []
  }

  async function openConversation(id) {
    loading.value = true
    try {
      const conv = await getConversation(id)
      currentId.value = id
      messages.value = conv.messages || []
    } finally {
      loading.value = false
    }
  }

  async function removeConversation(id) {
    await deleteConversation(id)
    if (currentId.value === id) newConversation()
    await loadList()
  }

  return { list, currentId, messages, loading, loadList, newConversation, openConversation, removeConversation }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm exec vitest run tests/useConversations.test.js`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useConversations.js frontend/tests/useConversations.test.js
git commit -m "feat: 前端会话状态composable(列表/新建/切换/删除/加载)"
```

---

### Task 6: 侧边栏 `components/Sidebar.vue`

**Files:**
- Create: `frontend/src/views/chat/components/Sidebar.vue`
- Test: `frontend/tests/sidebar.test.js`

**Interfaces:**
- Consumes: 无（纯展示组件，props/emit）。
- Produces: `<Sidebar :conversations :current-id @new @select @remove>`；`conversations` 为 `[{conversation_id,title,updated_at,message_count}]`。

- [ ] **Step 1: 写失败测试** `frontend/tests/sidebar.test.js`

```js
// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import Sidebar from '../src/views/chat/components/Sidebar.vue'

const conversations = [
  { conversation_id: 'c1', title: '新生报到', updated_at: '2026-08-20 10:00:00', message_count: 2 },
  { conversation_id: 'c2', title: '奖学金评定', updated_at: '2026-08-19 09:00:00', message_count: 4 },
]

function mountSidebar(props = {}) {
  return mount(Sidebar, {
    props: { conversations, currentId: 'c1', ...props },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('Sidebar', () => {
  it('渲染会话列表与新会话按钮', () => {
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('新会话')
    expect(wrapper.text()).toContain('新生报到')
    expect(wrapper.text()).toContain('奖学金评定')
  })

  it('点新会话触发 new 事件', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.new-btn').trigger('click')
    expect(wrapper.emitted('new')).toBeTruthy()
  })

  it('点会话触发 select 事件带 id', async () => {
    const wrapper = mountSidebar()
    await wrapper.findAll('.conv-item')[1].trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual(['c2'])
  })

  it('删除确认后触发 remove 事件带 id', async () => {
    const wrapper = mountSidebar()
    wrapper.findComponent({ name: 'ElPopconfirm' }).vm.$emit('confirm')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('remove')[0]).toEqual(['c1'])
  })

  it('空列表显示空态', () => {
    const wrapper = mountSidebar({ conversations: [] })
    expect(wrapper.text()).toContain('暂无历史会话')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm exec vitest run tests/sidebar.test.js`
Expected: FAIL — `Failed to resolve import '../src/views/chat/components/Sidebar.vue'`

- [ ] **Step 3: 写最小实现** `frontend/src/views/chat/components/Sidebar.vue`

```vue
<template>
  <aside class="sidebar">
    <button class="new-btn" type="button" @click="$emit('new')">+ 新会话</button>
    <ul class="conv-list">
      <li v-for="c in conversations" :key="c.conversation_id" class="conv-item"
          :class="{ active: c.conversation_id === currentId }"
          @click="$emit('select', c.conversation_id)">
        <span class="title" :title="c.title">{{ c.title }}</span>
        <el-popconfirm title="删除该会话？" width="180" @confirm="$emit('remove', c.conversation_id)">
          <template #reference>
            <span class="del" @click.stop>×</span>
          </template>
        </el-popconfirm>
      </li>
    </ul>
    <p v-if="!conversations.length" class="empty">暂无历史会话</p>
  </aside>
</template>

<script setup>
defineProps({
  conversations: { type: Array, default: () => [] },
  currentId: { type: String, default: null },
})
defineEmits(['new', 'select', 'remove'])
</script>

<style scoped>
.sidebar {
  width: 240px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}
.new-btn {
  margin: 12px;
  padding: 8px 12px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  background: #ecf5ff;
  color: #409eff;
  cursor: pointer;
  font-size: 14px;
}
.conv-list {
  flex: 1;
  overflow-y: auto;
  list-style: none;
  margin: 0;
  padding: 0 8px;
}
.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  color: #303133;
}
.conv-item:hover { background: #f0f2f5; }
.conv-item.active { background: #e6f4ff; }
.title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}
.del { color: #c0c4cc; margin-left: 8px; }
.del:hover { color: #f56c6c; }
.empty { padding: 16px; color: #909399; font-size: 13px; }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm exec vitest run tests/sidebar.test.js`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/chat/components/Sidebar.vue frontend/tests/sidebar.test.js
git commit -m "feat: 问答端侧边栏(新会话/历史会话列表/删除)"
```

---

### Task 7: ChatView 两栏集成

**Files:**
- Modify: `frontend/src/views/chat/ChatView.vue`
- Modify: `frontend/tests/chatView.test.js`（加 Sidebar stub + mock chat api）
- Test: `frontend/tests/chatConversation.test.js`

**Interfaces:**
- Consumes: Task 4 `askChat`（新签名）、Task 5 `useConversations`、Task 6 `Sidebar`。
- Produces: ChatView 两栏布局；`send()` 用 `currentId` 传 conversation_id、`onDone` 收新 id 刷新列表；挂载时 `loadList()`。

- [ ] **Step 1: 写失败测试** `frontend/tests/chatConversation.test.js`

```js
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import ChatView from '../src/views/chat/ChatView.vue'

vi.mock('../src/api/chat', () => ({
  askChat: vi.fn(),
  listConversations: vi.fn().mockResolvedValue([]),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
}))

import { askChat, listConversations } from '../src/api/chat'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div>chat</div>' } },
    { path: '/admin', component: { template: '<div>admin</div>' } },
  ],
})

function mountView() {
  return mount(ChatView, {
    global: {
      plugins: [ElementPlus, router],
      stubs: { TopicSelect: true, MessageList: true, Sidebar: true },
    },
    attachTo: document.body,
  })
}

describe('ChatView 会话集成', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('挂载时加载会话列表', async () => {
    listConversations.mockResolvedValue([{ conversation_id: 'c1', title: 't', updated_at: '', message_count: 1 }])
    mountView()
    await router.isReady()
    await new Promise((r) => setTimeout(r, 0))
    expect(listConversations).toHaveBeenCalled()
  })

  it('新会话发消息传 conversation_id=null 并在 done 记新 id', async () => {
    const wrapper = mountView()
    await router.isReady()
    askChat.mockImplementation((q, topic, cid, cb) => {
      cb.onDone?.({ conversation_id: 'new123' })
      return Promise.resolve()
    })
    await wrapper.find('textarea').setValue('新生报到')
    await wrapper.find('button.el-button--primary').trigger('click')
    expect(askChat).toHaveBeenCalledWith('新生报到', null, null, expect.any(Object))
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm exec vitest run tests/chatConversation.test.js`
Expected: FAIL — `askChat` 未按新签名调用（`currentId` 未接入 / 仍传 history）

- [ ] **Step 3: 写最小实现** `frontend/src/views/chat/ChatView.vue`

模板改为两栏（Sidebar + 现有 chat-view），`script` 接入 useConversations：

```vue
<template>
  <div class="chat-layout">
    <Sidebar :conversations="list" :current-id="currentId"
             @new="newConversation" @select="openConversation" @remove="removeConversation" />
    <div class="chat-view">
      <header class="chat-header">
        <h2 class="chat-title">校务智能问答</h2>
        <TopicSelect v-model="topic" :disabled="sending" />
        <router-link class="admin-entry" to="/admin">管理端</router-link>
      </header>
      <main class="chat-body">
        <div v-if="!messages.length" class="welcome">
          <h2>你好，我是校务智能助手</h2>
          <p class="welcome-tip">基于广州大学校务知识库作答，回答附来源。可以从这些示例开始：</p>
          <div class="examples">
            <el-button v-for="q in EXAMPLES" :key="q" round @click="send(q)">{{ q }}</el-button>
          </div>
        </div>
        <MessageList v-else :messages="messages" />
      </main>
      <footer class="chat-input">
        <el-input v-model="input" type="textarea" :autosize="{ minRows: 1, maxRows: 6 }"
                  placeholder="输入你的校务问题（Enter 发送，Shift+Enter 换行）"
                  :disabled="sending" @keydown.enter.exact.prevent="send(input)" />
        <el-button type="primary" :loading="sending" :disabled="!input.trim() || sending" @click="send(input)">发送</el-button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { askChat } from '../../api/chat'
import { useConversations } from '../../composables/useConversations'
import MessageList from './components/MessageList.vue'
import TopicSelect from './components/TopicSelect.vue'
import Sidebar from './components/Sidebar.vue'

const EXAMPLES = [
  '2026年新生报到需要带什么材料？',
  '港澳生如何申请校内宿舍？',
  '奖学金评定需要满足哪些条件？',
]

const topic = ref('')
const input = ref('')
const sending = ref(false)
const { list, currentId, messages, loadList, newConversation, openConversation, removeConversation } = useConversations()

onMounted(() => { loadList() })

function send(text) {
  const query = String(text || '').trim()
  if (!query || sending.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: query })
  const assistant = reactive({ role: 'assistant', content: '', sources: [], loading: true, error: false, empty: false })
  messages.value.push(assistant)
  sending.value = true

  askChat(query, topic.value || null, currentId.value, {
    onChunk(delta) { assistant.content += delta },
    onSources(sources) { assistant.sources = sources; assistant.loading = false },
    onDone(info) {
      assistant.loading = false
      sending.value = false
      if (info?.conversation_id && !currentId.value) {
        currentId.value = info.conversation_id
        loadList()
      }
    },
    onEmpty(message) {
      assistant.content = message; assistant.empty = true
      assistant.loading = false; sending.value = false
    },
    onError(message) {
      assistant.content = message; assistant.error = true
      assistant.loading = false; sending.value = false
    },
  }).finally(() => { assistant.loading = false; sending.value = false })
}
</script>

<style scoped>
.chat-layout { display: flex; height: 100svh; }
.chat-view { flex: 1; display: flex; flex-direction: column; height: 100svh; text-align: left; background: #fff; min-width: 0; }
.chat-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 24px; border-bottom: 1px solid #e4e7ed; }
.chat-title { margin: 0; font-size: 18px; color: #303133; }
.chat-body { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.welcome { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 24px; text-align: center; }
.welcome h2 { margin: 0; color: #303133; }
.welcome-tip { margin: 0; color: #909399; font-size: 14px; }
.examples { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 8px; }
.examples .el-button + .el-button { margin-left: 0; }
.chat-input { display: flex; align-items: flex-end; gap: 12px; padding: 14px 24px; border-top: 1px solid #e4e7ed; }
.chat-input .el-input { flex: 1; }
.admin-entry { font-size: 14px; color: #409eff; text-decoration: none; white-space: nowrap; }
</style>
```

同时改 `frontend/tests/chatView.test.js`（否则 Sidebar 真渲染会调 listConversations 报错），完整新内容：

```js
// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import ChatView from '../src/views/chat/ChatView.vue'

vi.mock('../src/api/chat', () => ({
  askChat: vi.fn(),
  listConversations: vi.fn().mockResolvedValue([]),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div>chat</div>' } },
    { path: '/admin', component: { template: '<div>admin</div>' } },
  ],
})

function mountView() {
  return mount(ChatView, {
    global: {
      plugins: [ElementPlus, router],
      stubs: { TopicSelect: true, MessageList: true, Sidebar: true },
    },
  })
}

describe('ChatView 双端入口', () => {
  it('页头提供管理端入口链接，指向 /admin', async () => {
    const wrapper = mountView()
    await router.isReady()
    const link = wrapper.find('a[href="/admin"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('管理端')
  })
})
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm exec vitest run tests/chatConversation.test.js tests/chatView.test.js`
Expected: PASS (2 + 1 = 3 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/chat/ChatView.vue frontend/tests/chatView.test.js frontend/tests/chatConversation.test.js
git commit -m "feat: ChatView两栏集成(侧边栏+会话状态,发消息带conversationId)"
```

---

### Task 8: 文档同步 + 全量回归

**Files:**
- Modify: `README.md`（功能清单 + 验收数字）
- Modify: `docs/PROGRESS.md`（追加多轮会话完成记录）

- [ ] **Step 1: 全量回归后端**

Run: `$env:DEEPSEEK_API_KEY=[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User'); uv run pytest tests/ -q`
Expected: 全绿（原 73 + 新增 7 + 4 + 3 = **87 passed**）

- [ ] **Step 2: 全量回归前端**

Run（`frontend/` 目录）: `pnpm exec vitest run` 然后 `pnpm build`
Expected: vitest 全绿（原 13 + 3 + 5 + 5 + 2 = **28 passed**）；build 成功（`✓ built`）

- [ ] **Step 3: 更新 README**

在功能清单「问答端」加一行：

```markdown
- 多轮会话：历史会话持久化（MongoDB）、左侧边栏查看/切换/删除、新会话（豆包式）
```

验收状态数字改为：后端 **87 passed**、前端 build ✅ + **28 passed**。

- [ ] **Step 4: 更新 PROGRESS.md**

在「人工数据入库」段落之后追加「多轮会话（2026-08-20）」段落：记录 8 个 commit、方案 A 后端权威、conversations 集合、/chat 契约变更、前端 Sidebar+useConversations、测试数字。

- [ ] **Step 5: Commit + push**

```bash
git add README.md docs/PROGRESS.md
git commit -m "docs: 多轮会话完成(后端87/前端28)+README/PROGRESS同步"
git push origin main
```
