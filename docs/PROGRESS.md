# 项目进度交接（PROGRESS.md）

> 跨会话续接的权威状态文件：任何会话接手本项目，先读本文件 + `AGENTS.md` + `docs/superpowers/plans/2026-08-18-backend-core.md`，即可无缝继续。

## 一句话

面向校务管理的 AI 自动数据采集与知识管理中台（广州大学校务信息聚合 + 附来源可信问答），三服务分层（collector/qa_api/model_server）+ 双端前端。

## 全局文档索引

| 文档 | 路径 | 作用 |
|------|------|------|
| Spec（需求真相） | `docs/superpowers/specs/2026-08-18-school-knowledge-hub-design.md` | 需求/架构/降级/验收 |
| ADR（决策真相） | `docs/adr/ADR-001..011` | 技术选型与派活约定 |
| 开发公约 | `AGENTS.md` | 模型分工/TDD/纪律（强制） |
| Plan 1（后端实现计划） | `docs/superpowers/plans/2026-08-18-backend-core.md` | 阶段 A/B/C 共 17 个 TDD 任务，含完整代码与测试 |

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

**测试状态：33 passed**。**后端 Plan 1 全部完成**（阶段 A/B/C 共 17 任务 + 2 处评审修复）。

冒烟验证记录：model_server `/health` ✅；collector 采集源 CRUD 全链路 ✅；qa_api `/health` ✅、`/chat` SSE 返回 `event: empty`（模型服务不在时降级诚实回答）✅。

### 待执行 ⏳

1. **Plan 2（前端）**：管理端 + 问答端（Vue3 + Element Plus + markstream-vue，SSE 对接），派 **kimi-k3**——**计划尚未编写**。
2. **Plan 3**：模拟数据脚本（六大专题域）+ 集成测试 + 打包交付——**尚未编写**。
3. **端到端联调**：真实采集（gzhu/gznews）→ 入库 → 问答全链路（需 model_server 启动 + BGE 权重路径正确）。

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

- 批次 1 派发 glm-5.3：B1B2 agent 成功；B3B4 agent 中途失败（B3 产出但未提交，B4 未做）→ 主会话收尾提交 B3、重派 B4 单任务仍失败（null）→ **主会话直接接管完成 B4**（4 passed）。
- 结论：glm-5.3 可产出但稳定性一般；**子代理失败后主会话直接接管补做，不反复重派空转**。批次 2 派发时 workflow 曾被取消（用户打断），重启即可。
- 已发现的计划实现注意点：motor 为异步驱动（所有 Mongo 调用必须 await）；selectolax 的 css() 对逗号选择器不去重（用单选择器等价实现）。

## 验证命令速查

```powershell
uv run pytest tests/ -v        # 全量测试
uv run uvicorn model_server.main:app --port 8001   # 模型服务
uv run uvicorn collector.main:app --port 8002      # 采集服务（B8 后）
uv run uvicorn qa_api.main:app --port 8003         # 问答服务（C4 后）
```

## 铁律提醒（立项三问）

① 答案可信：100% 来源引用，无来源不编造；② 单机稳定复现：一条 `docker compose up`；③ 零内网依赖：公网 + 模拟数据。
