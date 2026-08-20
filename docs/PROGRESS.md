# 项目进度交接（PROGRESS.md）

> 跨会话续接的权威状态文件：任何会话接手本项目，先读本文件 + `AGENTS.md` + 对应 Plan 文件（`docs/superpowers/plans/2026-08-18-backend-core.md` / `2026-08-19-plan3-demo-data-integration-delivery.md`），即可无缝继续。

## 一句话

面向校务管理的 AI 自动数据采集与知识管理中台（广州大学校务信息聚合 + 附来源可信问答），三服务分层（collector/qa_api/model_server）+ 双端前端。

## 全局文档索引

| 文档 | 路径 | 作用 |
|------|------|------|
| Spec（需求真相） | `docs/superpowers/specs/2026-08-18-school-knowledge-hub-design.md` | 需求/架构/降级/验收 |
| ADR（决策真相） | `docs/adr/ADR-001..011` | 技术选型与派活约定 |
| 开发公约 | `AGENTS.md` | 模型分工/TDD/纪律（强制） |
| Plan 1（后端实现计划） | `docs/superpowers/plans/2026-08-18-backend-core.md` | 阶段 A/B/C 共 17 个 TDD 任务，含完整代码与测试 |
| Plan 3（交付实现计划） | `docs/superpowers/plans/2026-08-19-plan3-demo-data-integration-delivery.md` | D1~D3 模拟数据与质量 / E1~E2 集成与降级 / F1~F3 打包交付，8 任务 TDD |
| 作品说明书 | `docs/作品说明书.md` | 定位/创新点/架构/验收（交付物） |
| 演示视频脚本 | `docs/演示视频脚本.md` | 8 镜 5 分钟路演脚本（交付物） |
| 20 题演示清单 | `docs/demo/20-questions.md` | 路演问答素材 + 来源引用率验收 |

## 当前进度

### 已完成 ✅

| 阶段 | 内容 | commits |
|------|------|---------|
| 立项/规格 | spec + 11 条 ADR + AGENTS.md | aa26af1 / b2f762a / ec997fc |
| Plan 1 编写 | 阶段 A/B/C 全部 17 任务（TDD 完整） | 0606ea5 |
| A1 骨架 | pyproject(uv) + .env.example + shared/config | 1e76cfc |
| A2 shared | 单例/异常/重试/日志 + pytest 配置 | 070d511 |
| A3 model_server | BGE-M3 双向量 + bge-reranker-large，/health 冒烟通过 | 692bc21 |
| A4 compose | milvus/mongo/minio/etcd 编排，语法验证通过 | 804148f |
| B1 站点适配器 | gzhu + gznews 适配器 | e5c2865 |
| B2 爬虫引擎 | 引擎+增量去重（URL/内容哈希+simhash） | 108023e |
| B3 解析模块 | trafilatura + LLM 兜底 | 334787b |
| B4 打标模块 | 一级规则 + 专题域 LLM 批量 | 8ac7abe |
| B5 时效模块 | 截止日期识别 + 默认有效期 | 4776b32 |
| B6 切分+入库 | 幂等先删后插 + MinIO 降级 | 7895546 |
| B7 调度状态机 | 任务状态机 + APScheduler + 采集源存储 | 2150421 |
| B8 管理端 API | 采集源/任务/知识库/统计/到期检测 + main | 324e874 |
| B 修复 | 采集源 CRUD motor 补 await（评审抓到） | f57110f |
| C1 混合检索 | 双路融合 + 时间衰减 + 过期降权 | 2845ce4 |
| C2 重排 | reranker 精排 + 断崖截断 + 降级 | d58892f |
| C3 生成 | 提示词 + LLM 主备降级流式 | c7b3884 |
| C4 问答 API | /chat SSE + 来源引用 + 问答日志 | 33bbb53 |
| C 收尾 | compose 追加 collector/qa-api 服务 | 292e0b6 |
| D1 测试补齐 | collector /health + 调度器/tasks API 测试（6 用例） | bb72770 |
| D2 打标兜底 | 规则词表扩充 + 专题域规则兜底 | cd9acbc |
| D3 模拟数据 | 六大专题域 18 篇模拟播种脚本 | 599a6cd |
| D 批修复 | MinIO 流对象 / seed 单事件循环（真跑暴露） | 0f1b426 / cd473d4 |
| E1 集成测试 | mock 站点 5 篇真跑全链路 + motor 隔离修复 | b2c5465 / 530f71c |
| E2 降级测试 | reranker 兜底 / LLM 主备切换 3 用例 | e9f5777 |
| F1 容器化 | 前端 Dockerfile+nginx 双端代理 + compose 全栈 + README | 633486a |
| F2 演示清单 | 20 题清单（六大专题域+综合） | a96cf02 |
| F3 交付文档 | 作品说明书 + 演示视频脚本 + PROGRESS 收尾 | 见最新 commit |

**测试状态：后端 73 passed（含真实 LLM 集成段 + 人工入库）；前端 build ✅ + vitest 13 passed；20 题来源引用率 20/20 = 100%**。**全部阶段完成**（Plan 1 阶段 A/B/C 17 任务、前端 Plan 2 F1~F7、Plan 3 D/E/F 8 任务、人工入库 5 任务）；全栈 compose 一条命令起实测通过。

冒烟验证记录：model_server `/health` ✅；collector 采集源 CRUD 全链路 ✅；qa_api `/health` ✅、`/chat` SSE 返回 `event: empty`（模型服务不在时降级诚实回答）✅；前端 5 路由全 200、build+vitest 通过 ✅。

### 待执行 ⏳

1. **Plan 3**：✅ 已完成（D/E 批派 glm-5.3 + 主会话核验接管；F 批主会话直接执行）。
2. ~~打标质量优化~~：已并入 Plan 3 D2（规则词表扩充 + 专题域规则兜底 + 复采验证）✅。
3. ~~评审遗留 B7/B8 测试~~：已并入 Plan 3 D1（调度器注册 + tasks API + collector /health）✅。
4. **后续可选（不在计划内）**：演示视频实际录制（脚本已备）；知识库人工修正/上下架的评审交互打磨；gznews 采集 4 篇失败页面的人工核查。

## 端到端联调记录（2026-08-19 实测跑通 ✅）

真实采集 gzhu 通知公告 8 篇 → 解析/打标 → Milvus+Mongo+MinIO 入库 → 问答全链路（chunk→sources→done）出带来源引用答案。联调暴露并修复 **7 个单元测试绿但真跑挂的 bug**（commit db50235→05f374f）：

1. 爬虫引擎缺浏览器 UA → 官网 403
2. gzhu 文章 URL 拼到列表页目录 → 404（补测试断言）
3. /embed 返回 numpy.float32 无法 JSON 序列化
4. ensure_collection 为零调用死代码（mock 测试绕过）→ Milvus 集合不存在
5. MilvusClient 新版 create_index 需 prepare_index_params；已存在集合需确保 load
6. FlagEmbedding 1.4.0 + transformers 5.x 接口漂移 → /rerank 手写交叉编码推理绕开
7. dense IVF_FLAT nlist=128 对小数数据空召回 → 改 AUTOINDEX；rerank 冷启动超时 → 30s

**关键环境事实**：DEEPSEEK_API_KEY 在 Windows 用户级环境变量中，DSH 沙箱进程不继承——DSH 起服务需先 `$env:DEEPSEEK_API_KEY=[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')`；用户自己开终端跑不受影响。transformers 需 4.52.x（uv 托管已装，5.x 会破坏 FlagEmbedding）。

## 后续修复与运行移交（2026-08-19 下午）

- `6056096`：**SSE CRLF 修复**——后端 sse_starlette 发 `\r\n` 换行，前端 sseFetch 只按 `\n\n` 分块导致浏览器端事件积压静默失败（curl 直测正常掩盖了此 bug）。sseFetch 读流时统一 `replace(/\r\n?/g,'\n')` 再分块，补 CRLF 单测（前端 8 passed）。
- `81a7406`：**问答端补管理端入口**——首页页头加「管理端」链接跳 `/admin`（此前双端无互跳入口）。TDD：先写组件测试看它失败再实现；新增 `frontend/tests/chatView.test.js`（@vue/test-utils + jsdom，前端 9 passed）。

## Plan 3 执行（2026-08-19 晚，阶段 D 完成）
- 派活记录：workflow 三连（D1 成功、D2/D3 空转零产出→主会话接管补做）；环境重启（用户三服务+存储已停：Docker Desktop 停→DSH 侧重启存储容器 + 本机起 model_server:8001）。
- `bb72770`（D1 子代理）：collector 补 `/api/health` + 调度器注册/tasks API 自动化测试（6 用例）。
- `cd9acbc`（D2 主会话）：打标规则词表扩充 + 专题域规则兜底 `rule_tag_topics`（tasks.py 中 `topics_map.get(url) or rule_tag_topics(...)`）。
- `599a6cd`（D3 主会话）：六大专题域模拟播种 `scripts/seed_demo.py`（内置模板 18 篇，幂等先删后插）。
- `0f1b426`（真跑暴露的存量 bug，TDD 修复）：MinIO 快照上传必须传流对象（`io.BytesIO`）而非 bytes（`'bytes' object has no attribute 'read'`）。
- `cd473d4`：seed 入口单事件循环（两次 `asyncio.run` 撞 motor 全局执行器）。
- **D 批验收证据**：复采真跑 8/8 成功且 MinIO 快照无缺失；Mongo `documents=26 with_topics=26 snapshot_missing=0`（8 真实 gzhu + 18 演示，专题全部非空）；seed 两轮 18=18 幂等；后端全量 48 passed。
- 环境移交注意：本会话起的 storage+model_server 仍在运行；用户自起三服务时直接 `uv run uvicorn ...` 即可（8001-8003 当前空闲），重启后 collector 即带 D2 规则兜底。

## Plan 3 阶段 E 完成（2026-08-19 深夜）
- `b2c5465`（E1 子代理）：`tests/integration/test_full_pipeline.py`（mock 站点 5 篇真跑：采集→打标→三写入库→混合检索→来源→LLM 问答）+ pyproject 注册 integration marker。
- `e9f5777`（E2 子代理）：`tests/test_degradation.py`（reranker 挂原序兜底 / LLM 主备切换 / 主备全挂报错，3 用例，回归锁定）。
- `530f71c`（E1 真跑暴露的测试隔离问题，主会话修复）：motor 单例跨 pytest-asyncio 函数级循环在 Windows 崩（Event loop is closed）→ fixture 里 `get_mongo.cache_clear()`。
- **E 批验收证据**：E1 真跑（注入用户级 DEEPSEEK_API_KEY）2 passed 含真实 LLM 生成；E2 3 passed；后端全量 52 passed + 1 skipped（skip=无 key 时的 LLM 段，设计使然）。
- **环境新事实**：DSH 沙箱 workspace-write 模式**拒绝修改/删除非本会话创建的既有文件**（node_modules 由用户早上安装，pnpm add 重链时反复「Failed to remove」挂死）；会话文件策略升 danger-full-access 后安装 3.5s 完成。凡需动既有 node_modules/构建产物的命令，需该策略。子代理（kimi-k3）本轮再次空转零产出（仅留 .pnpm-store 垃圾），主会话已接管完成。
- 运行移交：三后端服务已由用户自行启动验证（DSH 侧已停、端口释放）。知识库保留 8 篇 gzhu 真实文档 + 已启用采集源 f1bfb927f134（每 6h 自动增量采集）。
- **新会话接手一句话**：读本文件 + `AGENTS.md` + Plan 文件，然后从「Plan 3」开始。

## Plan 3 阶段 F 完成（2026-08-20 凌晨，项目收官 ✅）

- `633486a`（F1）：前端容器化（Dockerfile 双段构建 + nginx 双端反代/SSE 不缓冲/SPA fallback）+ compose 追加 frontend + README 一条命令起全栈。
- `a96cf02`（F2）：20 题演示问题清单（六大专题域 18 题 + 综合 2 题）。
- F3（最新 commit）：`docs/作品说明书.md` + `docs/演示视频脚本.md` + PROGRESS/README 终态同步。
- **F1 真跑修复清单**（Docker Desktop + 国内网络踩坑）：① BuildKit token 拉取走 IPv6 超时 → 先用 `docker pull` 预拉基础镜像再 build；② pnpm@11 需 Node ≥22.13（node:sqlite）→ 基础镜像 node:22-alpine；③ 容器内 npm/pip 直连官方源不可达 → 显式加 npmmirror/清华镜像；④ 后端 Dockerfile 按仓库根上下文 COPY（compose 原 build 指向子目录从未构建过）→ 三服务 build 块改 context:.+dockerfile；⑤ collector Dockerfile 漏 simhash → 补包；⑥ 根 .dockerignore 防 node_modules 进上下文。
- **F2 空环境复测实测**：compose 起全栈 → 前端 `/` 与 `/admin` SPA 断言 ✅ → `/admin-api/api/health` 与 `/qa-api/api/health` 经 nginx 200 ✅ → 容器内播种 18 篇模拟 + gzhu 8 篇 + gznews 11 篇真实采集（4 篇失败隔离）→ **20 题逐题 SSE 实测 20/20 附来源引用（100%）** → 后端 53 passed（含真实 LLM）→ 前端 build 0 + 9 tests。
- **重大环境发现（双存储，务必知晓）**：本机 127.0.0.1:9000/19530/27017 由 `wslrelay.exe`（WSL2）独占中继 → 宿主机进程（uv run）连 localhost 打的是 **WSL 里的真实存储**（知识库数据在那边）；Docker Desktop compose 起的是**另一套独立存储**（容器网络内部互通，全新）。两套各自自洽：宿主机三服务+真实库 / compose 全栈+容器库。宿主机要打容器库需绕 127.0.0.1（用局域网 IP 或进容器 exec）。**演示（compose 一条命令）默认用容器库，从空库起：播种+建源+采集即可复现 20/20。**
- 派活记录：F 批按计划主会话直接执行（未派 workflow）。
- **项目收官结论**：Plan 1/2/3 全部完成，8 任务 TDD 逐项核验磁盘/测试/commit 通过；剩余可选事项见「待执行」第 4 条。

## 人工数据入库（2026-08-20，录入+上传+编辑/删除 ✅）

- 背景：补齐第三条入库路径——人工主动补充知识（此前仅自动采集 + 脚本播种）。spec `docs/superpowers/specs/2026-08-20-manual-data-ingestion-design.md`、plan `docs/superpowers/plans/2026-08-20-manual-data-ingestion.md`。
- 5 任务 TDD（每任务最小改动 commit）：`8493a56` ingest_document 显式 doc_id → `9ba6953` file_parser（pypdf/python-docx）→ `ed153b4` manual.py 编排（create/update 幂等覆盖/delete 清三处）→ `cf2a85f` manual API（parse-file/documents 增删改）+ 路由 + 容器依赖（含 python-multipart）→ `a1375cd` 前端表单/编辑/删除（request 支持 FormData）。
- 数据标识：`source_site="manual"`、doc_id=`uuid4().hex[:16]` 稳定复用、无来源 url 占位 `manual://{doc_id}`（前端不跳转）、分类/专题未填走规则、publish_date 空回退今天。
- 后端 +18 用例（**73 passed**）；前端 +2 用例（**13 passed**）+ build ✅。
- 真跑验收（容器 rebuild 后）：录入 → source_site=manual/url 保留 → 详情 200；编辑复用 doc_id 正文更新（含「寒暑假」）；上传 txt 解析+入库+删除（deleted:true + 404）；问答「图书馆借阅规则」召回 manual 文档附来源（lib.gzhu.edu.cn/rules.htm）。
- 派活记录：按 AGENTS.md 先派 workflow（glm-5.3 后端 4 任务），再次空转（4 agent 全 null、仅 Task1 半途写测试）；主会话接管逐任务 TDD 完成。**再次印证：workflow 派 glm-5.3 在本项目持续空转，后续功能建议主会话直接执行。**

## 多轮会话（2026-08-20，历史持久化 + 侧边栏 ✅）

- 背景：问答端加「多轮会话 + 历史会话持久化 + 侧边栏」（豆包式：新建/切换/删除，刷新不丢）。spec `docs/superpowers/specs/2026-08-20-multi-turn-conversations-design.md`、plan `docs/superpowers/plans/2026-08-20-multi-turn-conversations.md`。
- 方案 A 后端权威：会话落 MongoDB `conversations` 单集合（内嵌 `messages`）；`conversation_id=uuid4().hex[:16]`；`title=query[:20]`（超长加 `…`）仅建会话时写一次；上下文沿用 `llm.py` 已有 `history[-6:]`（不改生成层）。
- `/chat` 契约变更：`{query, topic, history}` → `{query, topic, conversation_id}`（后端读会话拼历史）；`done` 事件 data 新增 `conversation_id`；会话落库失败 try/except 降级（done 仍返回、id 为 null）。
- 8 任务 TDD（每任务最小改动 commit）：`65a0b09` 会话业务函数（依赖注入 db）→ `0c62d86` 会话 API（列表/详情/删除 404）→ `af3c2b2` /chat 改契约+落库 → `2323bd9` 前端会话 API → `61df52b` useConversations composable → `4895a42` Sidebar（新会话/列表/删除 popconfirm）→ `72b27a1` ChatView 两栏集成（发消息带 conversationId，done 记新 id 刷新列表）→ 文档同步（本 commit）。
- 后端 +14 用例（**87 passed**）；前端 +15 用例（**28 passed**）+ build ✅。
- 派活记录：主会话直接执行（遵循本文件已沉淀教训——workflow 派 glm-5.3 持续空转，见「人工数据入库」段）。

## 采集页数控制器（2026-08-20，已完成 ✅）

- 背景：当前一次采集只抓 `list_url` 一页（不翻页）。实测 gzhu 通知公告 85 条 9 页、gznews 头条关注 10399 条 694 页，单页仅 10~15 条，用户要求加「采集程度控制器」可调高采集更多页。
- 需求已确认：按**页数**档位 `1/3/5/10/全部`；「全部」内部封顶 `MAX_PAGES_CAP=50`；交付=后端+前端+测试+真跑；**通用性**——接入范围主要 gzhu 系网站，翻页抽象为适配器通用接口。
- 设计定稿（通用分层）：`SiteAdapter` 基类加 `next_page_url` 接口（默认 None=不翻页）→ 新增 `collector/crawler/gzhu_cms.py` 的 `GUZhuCMSAdapter` 实现「解析下页 a.Next 链接」（urljoin 拼绝对地址，末页返回 None）→ gzhu/gznews 适配器继承它；引擎 `fetch_source` 加 `max_pages` 翻页循环（`_seen` 去重跨页生效）；`SourceConfig` 加 `max_pages: int = 1`；前端 SourcesView 加「采集页数」下拉。
- **spec 已落盘**：`docs/superpowers/specs/2026-08-20-collection-pagination-control-design.md`（含探索结论/数据模型/设计/测试/范围外/验收，实现前必读）。
- 涉及文件：后端 `collector/sources.py`、`crawler/base.py`、`crawler/gzhu_cms.py`(新)、`crawler/gzhu.py`、`crawler/gznews.py`、`crawler/engine.py`、`tasks.py`、`api/sources.py`；前端 `frontend/src/views/admin/SourcesView.vue`（`admin.js` 无需改，payload 原样透传）；测试 `tests/test_pagination.py`、`tests/test_sources.py`、`tests/test_engine_pagination.py` + `frontend/tests/sourcesView.test.js`（新）。
- 6 任务 TDD（每任务最小改动 commit，主会话直接执行，未派 workflow）：`5a29f2d` plan → `b1960ca` 适配器 `next_page_url` 接口 + `gzhu_cms.py` 共享层（gzhu/gznews 继承）→ `80157e0` `SourceConfig.max_pages`（默认 1 向后兼容）+ create_source 透传 → `61ba98f` 引擎翻页循环（`MAX_PAGES_CAP=50` + `page_capped`，`fetch_source` 返回三元素元组）→ `b83943c` 任务编排透传 max_pages + 记录 page_capped → `290a17f` 前端采集页数下拉（1/3/5/10/全部）。
- **验收证据**：后端 `uv run pytest tests/`（注入 key）**101 passed**（+14 用例）；前端 vitest **34 passed** + build ✅；容器 `docker compose build collector frontend` + `up -d` 后真跑：建 `max_pages=3` 的 gzhu 源 → 采集结果 `succeeded=27 / failed=1 / page_capped=false`，容器 Mongo gzhu 文档 27 篇（> 单页 ~10 篇），`aggregate` 查重复 doc_id 分组 = **0**。
- 关键实现点：翻页只写在 `gzhu_cms.py` 适配器层（`urljoin` 拼相对 href，末页 `span.NextDisabled` 无 `a.Next` 返回 None），通用基类 `SiteAdapter.next_page_url` 默认 None 不污染站点选择器；`fetch_source` 三元素返回 `(articles, failures, page_capped)`，`_seen` 去重跨页生效；`page_capped` 仅「全部」档打到 `MAX_PAGES_CAP` 且仍有下页时为 True。

## 环境状态（本机开发）

| 项 | 状态 |
|----|------|
| 存储 | WSL Docker 运行中：Milvus `localhost:19530`、Mongo `localhost:27017`、MinIO `localhost:9000`（均实测连通） |
| `.env` | 已建（不进 git）：`BGE_M3_PATH=D:\ai_models\huggingface_cache\bge-m3\models\BAAI--bge-m3\snapshots\master`、`RERANKER_PATH=D:\ai_models\modelscope_cache\models\BAAI--bge-reranker-large\snapshots\master` |
| DeepSeek key | 在用户环境变量中（`os.getenv` 直读，无需写 .env）✅ |
| DashScope key | 占位符空值（降级路径代码保留，key 空时不影响主链路） |
| Python | uv 0.11.28 + Python 3.11（uv 托管），`uv run pytest` / `uv run uvicorn` |
| 冒烟注意 | Windows 上 localhost 可能解析到 IPv6，测试用 `http://127.0.0.1:<port>` |

## 派活执行记录（经验沉淀）

- 模型路由最终约定（用户 2026-08-19 拍板）：主会话 deepseek-v4-pro（调度/脚手架/规划/评审/集成）；后端 glm-5.3；前端 kimi-k3。已写入 AGENTS.md + ADR-011 + model-routing skill（含「验收铁律」：报告完成≠通过，逐任务核验文件/测试/commit）。
- **「假通过」事故记录**：多轮 workflow 返回 null/空报告但部分 agent 实际半途产出；F4/F5/F6 曾显示派发完成实为壳。处理：主会话接管补做 + 全任务逐项核查（发现 gznews 无测试覆盖已补）。**教训：每个派发批次完成后必须逐任务核验磁盘状态，不以 workflow 返回值/子代理报告为验收依据。**
- **子代理失败后主会话直接接管补做，不反复重派空转**。已发现的计划实现注意点：motor 为异步驱动（所有 Mongo 调用必须 await）；selectolax 的 css() 对逗号选择器不去重（用单选择器等价实现）。

## 验证命令速查

```powershell
uv run pytest tests/ -v        # 全量测试
uv run uvicorn model_server.main:app --port 8001   # 模型服务
uv run uvicorn collector.main:app --port 8002      # 采集服务（B8 后）
uv run uvicorn qa_api.main:app --port 8003         # 问答服务（C4 后）
```

## 铁律提醒（立项三问）

① 答案可信：100% 来源引用，无来源不编造；② 单机稳定复现：一条 `docker compose up`；③ 零内网依赖：公网 + 模拟数据。
