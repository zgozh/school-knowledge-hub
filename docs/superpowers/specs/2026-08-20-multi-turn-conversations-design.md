# 多轮会话设计（历史会话持久化 + 侧边栏）

> 状态：已确认（方案 A：后端权威）。本 spec 是「多轮会话」子系统的设计真相，实现前必读。
> 关联：spec `2026-08-18-school-knowledge-hub-design.md`（主 spec）、ADR-010（数据策略，Mongo 落库）、ADR-011（模型分工）。

## 1. 背景与目标

当前问答端只有「单页单轮」体验：`/chat` 已支持 `history` 参数做多轮生成、前端 `ChatView.vue` 也在内存里拼 history 传过去，但**会话不落库**——刷新即丢，也没有侧边栏查看历史会话、开始新会话的能力（对标豆包/微信式会话管理）。

本子系统补齐**会话管理**：多轮对话持久化到 MongoDB、左侧边栏展示历史会话列表、可新建/切换/删除会话。核心原则：**数据单一来源在后端**（前端只是视图），刷新后加载历史会话仍可无缝继续多轮。

## 2. 需求（已确认澄清结果）

1. **存储**：后端 MongoDB（非 localStorage），真持久、跨设备。
2. **操作**：新建 / 切换 / 删除 三项（标题自动取首条提问截断，**不做重命名**）。
3. **上下文窗口**：最近 6 条消息（沿用现有 `llm.py` 的 `history[-6:]` 截断，≈3 轮，零额外改动）。
4. **形态**：左侧 Sidebar（新会话按钮 + 历史会话列表）+ 右侧主对话区（现有 ChatView 主体）。
5. **刷新后**：拉列表渲染侧边栏，主区回「新会话」空白欢迎态；点历史会话加载其 messages 继续聊。
6. **不做 URL 路由**（豆包式：刷新回首页、历史在侧边栏；不做 /chat/:id 分享/深链）。

## 3. 数据模型

MongoDB `school_knowledge_hub.conversations` 集合（单集合内嵌 messages，不做 conversations+messages 双集合——单机单用户，YAGNI）：

```json
{
  "conversation_id": "a1b2c3d4e5f6a7b8",
  "title": "2026年新生报到需要带什么材料",
  "messages": [
    { "role": "user",      "content": "...", "created_at": "2026-08-20 10:00:00" },
    { "role": "assistant", "content": "...", "sources": [{ "doc_id": "...", "title": "...", "url": "...", "publish_date": "...", "category": "...", "expired": false }], "created_at": "..." }
  ],
  "created_at": "2026-08-20 10:00:00",
  "updated_at": "2026-08-20 10:00:05"
}
```

- `conversation_id`：`uuid4().hex[:16]`（与文档 doc_id 风格一致）。
- `title`：首条提问截断 20 字（`query[:20]` + 超长加 `…`），**仅建会话时写一次**，后续轮次不改。
- `messages`：每轮问答追加 `user` + `assistant` 两条；`sources` 仅 assistant 有（用于前端还原来源卡片）。
- `updated_at`：每次追加刷新，侧边栏按此倒序排列。

## 4. 后端设计

### 4.1 新 API `qa_api/api/conversations.py`（前缀 `/api/conversations`）

| 方法 | 路径 | 作用 | 返回 |
|------|------|------|------|
| GET | `/api/conversations` | 会话列表 | `[{conversation_id, title, updated_at, message_count}]`（**不含** messages 全量） |
| GET | `/api/conversations/{id}` | 会话详情 | 单条含 `messages` 全量；不存在返回 404 |
| DELETE | `/api/conversations/{id}` | 删除会话 | `{deleted: true}`；不存在也返回 `{deleted: true}`（幂等） |

- 无 POST（会话由 `/chat` 首条消息自动创建，避免「点新会话但不发消息」产生空会话）。
- 无 PUT（重命名已砍）。
- 列表按 `updated_at` 倒序，`message_count = len(messages)`。

### 4.2 `/chat` 改造（`qa_api/api/chat.py`）

`ChatRequest` 契约变更：

```python
class ChatRequest(BaseModel):
    query: str
    topic: str | None = None
    conversation_id: str | None = None   # 新增；移除原 history
```

事件流逻辑（生成 → 来源 → 落库 → done）：

1. 检索/重排/生成流程不变（每轮仍独立 `hybrid_search(req.query)`，history 只喂 LLM 生成、不参与检索）。
2. **拼 history**：`conversation_id` 有值 → `find_one` 查会话，取 `messages` 里 `{role, content}` 拼成 history（沿用 `stream_answer` 内部 `history[-6:]` 截断）；查不到或为空 → 空 history。
3. 生成完整 answer + 构造 sources 后（yield `sources` 事件之后、`done` 之前）**落库**：
   - `conversation_id` 为空或查不到 → 新建会话（`title = query[:20]`，超长加 `…`）→ 得新 `conversation_id`。
   - `conversation_id` 有效 → 追加本轮 `user` + `assistant`（含 sources）两条消息 → 刷新 `updated_at`。
4. `done` 事件新增 `conversation_id` 字段（新建时返回新 id，前端据此更新当前会话）。

> 会话落库失败（Mongo 异常）不阻断答案流：try/except 降级，`done` 仍正常返回（`conversation_id` 为 null），仅日志告警——对齐主链路「可选依赖不拖垮」铁律。

### 4.3 注册

`qa_api/main.py` 追加 `app.include_router(conversations.router)`。

## 5. 前端设计

### 5.1 布局

`ChatView.vue` 改为两栏：

```
┌──────────┬───────────────────────────┐
│ Sidebar  │  header（标题/专题/管理端入口）│
│ 新会话   │  main（welcome / MessageList）│
│ 会话列表 │  footer（输入框/发送）         │
└──────────┴───────────────────────────┘
```

### 5.2 新增 `components/Sidebar.vue`

- 「+ 新会话」按钮（置顶）。
- 会话列表：每条显示 `title`（超长省略）+ 相对时间；hover 右侧出删除按钮（`el-popconfirm` 确认）。
- 当前会话高亮。
- 空态提示「暂无历史会话」。

### 5.3 状态管理

不引 Pinia（YAGNI），新增 composable `composables/useConversations.js` 收敛会话逻辑，供 ChatView 使用：

- `list`（会话列表）、`currentId`、`messages`（当前会话消息）、`loading`。
- `loadList()` / `openConversation(id)` / `newConversation()` / `removeConversation(id)`。

### 5.4 API 层（`api/chat.js` 扩展）

```js
listConversations()                 // GET  /qa-api/api/conversations
getConversation(id)                 // GET  /qa-api/api/conversations/{id}
deleteConversation(id)              // DELETE /qa-api/api/conversations/{id}
askChat(query, topic, conversationId, callbacks)  // 去 history 参数；onDone 回调带 conversation_id
```

### 5.5 交互

- 新会话：清空 `messages` + `currentId=null`，主区显示 welcome；发首条消息后 `onDone` 拿到新 `conversation_id` → 更新 `currentId` + 刷新侧边栏列表。
- 切换：点侧边栏 → `getConversation(id)` → 渲染 messages（还原来源卡片）。
- 删除：`removeConversation(id)` → 刷新列表；若删的是当前会话则回新会话态。
- 刷新：`loadList()` 渲染侧边栏，主区回新会话态。

## 6. 数据流

1. **新会话**：点「新会话」→ 主区空白 → 发 `/chat {query, conversation_id:null}` → 后端生成 + 落库新会话 → `done.conversation_id` 返回 → 前端记 id、侧边栏出现该会话。
2. **继续聊**：发 `/chat {query, conversation_id}` → 后端取最近历史生成 → 追加落库 + 刷新 updated_at。
3. **切换**：点侧边栏 → `GET /conversations/{id}` → 渲染 messages + 设 currentId。
4. **删除**：hover 删除 → `DELETE /conversations/{id}` → 刷新列表（当前会话则回新会话态）。
5. **刷新**：拉列表渲染侧边栏，主区回新会话态。

## 7. 测试

- **后端**（pytest，`tests/test_conversations_api.py` + `tests/test_chat_conversation.py`）：
  - conversations API：列表（字段/排序/不含 messages 全量）、详情（含 messages/404）、删除（存在与不存在均幂等）。
  - `/chat` 落库：首条消息建会话（title 截断、done 返回 id）、带 id 追加消息且 title 不变、history 拼装、无效 id 按新会话处理。
- **前端**（vitest）：Sidebar（渲染列表/新会话/删除）、ChatView（切换/新建/刷新加载）。

## 8. 范围外（YAGNI，一律不做）

重命名会话、会话清空、用户体系/多用户/鉴权、会话搜索、会话导出、URL 深链（/chat/:id）、Pinia 状态库、conversations+messages 双集合、多端同步。

## 9. 验收标准

1. 后端全量 pytest 通过（含新增用例）；前端 vitest + build 通过。
2. 真跑：新建会话 → 连续多轮追问（答案带上下文）→ 刷新 → 侧边栏出现历史会话 → 点开继续多轮 → 删除会话。
3. 会话落库失败不阻断问答（降级仍返回答案，仅无 conversation_id）。
