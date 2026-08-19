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

**测试状态：35 passed**。**后端 Plan 1 全部完成**（阶段 A/B/C 共 17 任务 + 2 处评审修复）；**前端 Plan 2 全部完成**（F1~F7，每任务独立 commit）。

冒烟验证记录：model_server `/health` ✅；collector 采集源 CRUD 全链路 ✅；qa_api `/health` ✅、`/chat` SSE 返回 `event: empty`（模型服务不在时降级诚实回答）✅；前端 5 路由全 200、build+vitest 通过 ✅。

### 待执行 ⏳

1. **Plan 3**：已编写（8 任务 TDD，含全部测试/实现代码与验收步骤）——**待用户确认后按 ADR-011 派活执行**（D/E 批量派 glm-5.3，F 主会话）。
2. ~~打标质量优化~~：已并入 Plan 3 D2（规则词表扩充 + 专题域规则兜底 + 复采验证）。
3. ~~评审遗留 B7/B8 测试~~：已并入 Plan 3 D1（调度器注册 + tasks API + collector /health）。

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
