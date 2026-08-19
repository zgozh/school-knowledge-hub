# 人工数据入库设计（手动录入 + 文件上传 + 编辑/删除）

> 状态：已确认（方案 A）。本 spec 是「人工数据入库」子系统的设计真相，实现前必读。
> 关联：spec `2026-08-18-school-knowledge-hub-design.md`（主 spec）、ADR-008（采集管道）、ADR-010（数据策略）。

## 1. 背景与目标

「面向校务管理的 AI 自动数据采集与知识管理中台」当前只有两条入库路径：① 自动采集（gzhu/gznews 适配器）；② 脚本播种（`scripts/seed_demo.py`）。缺少**人工主动补充知识**的能力——校务人员无法把一份通知/制度/办事流程手工放进知识库并被问答检索。

本子系统补齐第三条入库路径：**人工数据入库**，让用户手动录入或上传文件，经现有分类/打标/时效/切分/向量化/三写入库管线，落地后立即可被问答端检索、附来源引用。

## 2. 需求（已确认澄清结果）

1. **形态**：手动录入表单 + 上传文件自动解析，两者都要。
2. **文件格式**：PDF、Word(.docx)、纯文本/Markdown（.txt/.md）。
3. **治理**：支持编辑（改正文/元数据后幂等覆盖）与删除（清三处存储）。
4. 入库后立即可检索/问答，复用现有 `ingest_document` 管线。

## 3. 数据模型与标识约定

- `source_site = "manual"`，`column` 默认 `"人工录入"`（用户可改）。
- **doc_id 稳定**：创建时后端生成 `uuid4().hex[:16]`；编辑时复用同一 doc_id（幂等覆盖，不产生新文档）。
- **url 字段**：用户填真实来源 URL 则存之；未填则存内部占位 `manual://{doc_id}`（不产生外链）。
  - 前端「打开原文」按钮仅在 url 为真实 `http(s)://` 且非 `https://demo.gzhu.edu.cn/` 前缀时显示；`manual://` 与 demo 域名一律不跳转。
- **分类/专题**：前端可手选覆盖；未选则后端规则自动打标（`classify_category(title, column)` + `rule_tag_topics(title, content)`）。
- **时效**：`infer_expiry(title, content, category, publish_date)`；`publish_date` 前端默认今天、后端空值回退今天（保证 `infer_expiry` 对通知公告类不因 None 崩溃）。

## 4. 后端设计

### 4.1 文件解析 `collector/parser/file_parser.py`（新，纯函数、可单测）

```python
def parse_file(filename: str, data: bytes) -> dict:  # -> {"title": str, "content": str}
```

- 按扩展名分派：
  - `.pdf` → `pypdf.PdfReader(BytesIO(data))` 逐页 `extract_text()` 拼接
  - `.docx` → `python-docx` `Document(BytesIO(data))` 遍历段落拼接
  - `.txt`/`.md` → `data.decode("utf-8")`，失败回退 `gbk`
  - 其他扩展名 → 抛 `ValueError("不支持的文件类型")`
- 标题默认取文件名去扩展名；解析后 content 为空 → 抛 `ValueError("文件解析结果为空")`。

### 4.2 业务编排 `collector/manual.py`（新）

沿用「API 薄 / 业务逻辑在 collector/*.py」分层（同 knowledge.py/tasks.py）：

```python
async def create_document(payload: dict) -> str:      # 生成 doc_id，打标/时效，ingest，返回 doc_id
async def update_document(doc_id: str, payload: dict) -> str | None:  # 复用 doc_id 重新 ingest；不存在返回 None
async def delete_document(doc_id: str) -> bool:        # 清 Mongo + Milvus + MinIO（容错）
```

- create/update 内统一构造 `ParsedArticle(url=payload.url or f"manual://{doc_id}", title, content, publish_date, department, source_site="manual", column=payload.column or "人工录入", raw_html=<标题+正文拼 HTML>)`。
- **update 字段回退规则**（先查原文档 `find_one({"doc_id": doc_id})`，不存在返回 None）：`title/content` 必填用 payload；`url = payload.url or 原文档.url`；`publish_date = payload.publish_date or 原文档.publish_date`；`department/column = payload 值 or 原文档值`；`category/topics` 未填则走规则重算（与 create 一致）。
- 打标：`category = payload.category or classify_category(title, column)`；`topics = payload.topics or rule_tag_topics(title, content)`；`expire_at = infer_expiry(title, content, category, publish_date)`。
- 调用 `ingest_document(parsed, category, topics, expire_at, doc_id=doc_id)`。
- delete：Mongo `documents.delete_many({"doc_id": doc_id})`；Milvus `delete(collection, filter=f'doc_id == "{doc_id}"')`；MinIO `remove_object(bucket, f"snapshots/{doc_id}.html")` 失败容错忽略。

### 4.3 API `collector/api/manual.py`（新，前缀 `/api/admin/manual`）

| 方法/路径 | 请求 | 响应 |
|-----------|------|------|
| `POST /manual/parse-file` | multipart `file`（≤10MB） | `{"title","content"}` 或 400 `{"detail"}` |
| `POST /manual/documents` | JSON：`title*`、`content*`、`category?`、`topics?[]`、`publish_date?`、`url?`、`department?`、`column?` | `{"doc_id"}` |
| `PUT /manual/documents/{doc_id}` | 同上 JSON | `{"doc_id"}` 或 404 |
| `DELETE /manual/documents/{doc_id}` | — | `{"deleted": true}` 或 404 |

- 文件大小超 10MB → 400「文件过大」；`publish_date` 空 → 今天。
- `collector/main.py` 注册 `manual_api.router`。

### 4.4 `ingest_document` 改动（`collector/ingest/writer.py`）

签名加可选 `doc_id: str | None = None`，函数内 `doc_id = doc_id or doc_id_of(parsed.url)`。**完全向后兼容**（现有调用不传 doc_id 走原逻辑）。

### 4.5 依赖

- `pyproject.toml` dependencies 加 `pypdf`、`python-docx`。
- `collector/Dockerfile` pip 安装列表加 `pypdf python-docx`（model_server/qa_api 不加）。

## 5. 前端设计

- **`KnowledgeView.vue`**：
  - 页头加「新增知识」按钮 → `el-dialog` 表单。
  - 正文来源 `el-radio`：手动录入（textarea）｜上传文件（`el-upload`，选中即调 `parse-file` 回填标题/正文）。
  - 字段：标题（必填）、正文（必填）、发布日期（`el-date-picker`，默认今天）、分类（下拉可选）、专题（多选可选）、来源 URL（可选）、发布部门（可选）。
  - 详情抽屉加「编辑」（打开同一表单回填当前详情）与「删除」（`el-popconfirm`）。
- **`api/admin.js`** 加 `manualApi = { parseFile, createDocument, updateDocument, removeDocument }`；**`useKnowledge.js`** 加 `getDetail/create/update/remove` 对应方法。
- 「打开原文」判定：`isExternalUrl(url)` = `url` 以 `http://`/`https://` 开头且非 `https://demo.gzhu.edu.cn/` 前缀；否则不显示跳转（`manual://` 与 demo 均不跳）。
- 文件大小限制 10MB（前端 + 后端双重校验）。

## 6. 数据流

1. **录入流**：填表单 → `POST /manual/documents` → 打标/时效 → `ingest_document`（切分→embedding→Mongo/Milvus/MinIO 三写）→ 立即可检索。
2. **上传流**：选文件 → `POST /manual/parse-file` → 回填表单 → 校对 → `POST /manual/documents` → 同录入流。
3. **编辑流**：详情抽屉「编辑」→ 表单回填 → `PUT /manual/documents/{doc_id}` → 幂等覆盖 → 新内容即时生效。
4. **删除流**：`DELETE /manual/documents/{doc_id}` → 三处清理 → 列表刷新。

## 7. 错误处理与降级

- 解析失败/格式不支持/空内容/超 10MB → 400 中文 `detail`，前端 `ElMessage` 提示，**不落任何脏数据**。
- embedding/模型服务不可用 → 沿用 `ingest_document` 现有语义（`_embed_batch` 抛错即整条入库失败），前端提示重试。
- 删除时 MinIO 对象缺失 → 容错忽略（快照可能本就有 `snapshot_missing` 标记）。

## 8. 测试策略（TDD，先失败再实现）

- 后端：
  - `tests/test_file_parser.py`：txt/md 解码、pdf/docx 解析（最小真实样本）、不支持格式抛错、空内容抛错。
  - `tests/test_manual_api.py`：parse-file 端点（mock `parse_file`）、create（mock `ingest_document`，验证 doc_id 生成/打标/时效/url 占位）、update（复用同 doc_id + 404）、delete（三处清理 mock + 404）。
  - `tests/test_ingest_idempotent.py` 补：显式 `doc_id` 参数生效。
- 前端：`frontend/tests/manualForm.test.js`：新增按钮打开表单、录入提交调 create、上传回填、编辑回填、删除调 remove。
- 全量回归：后端 `pytest`、前端 `vitest run`、`pnpm build`。

## 9. 范围外（YAGNI，第一版不做）

- 不做批量导入（一次一条）。
- 不做入库审核流（录入即 active，可后续上下架）。
- 不做文件多格式（Excel/HTML）、OCR/扫描件解析。
- 不做图片附件上传、不做富文本编辑（正文纯文本）。
- 不做权限/多用户（沿用现有无鉴权形态）。
