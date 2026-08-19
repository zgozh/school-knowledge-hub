# 校务知识中台（School Knowledge Hub）

> 面向校务管理的 AI 自动数据采集与知识管理中台

自动采集广州大学多源校务信息（通知公告、新闻网）构建知识库，师生用自然语言提问即可获得**100% 附来源引用**的可信答案。双端形态：管理端（采集治理）+ 问答端（自然语言问答）。

## 四大主题要素

| 要素 | 落点 |
|------|------|
| AI 自动数据采集 | 定时调度 + 站点适配器 + 爬取引擎 + 增量去重 + LLM 兜底解析 + 专题打标，全自动入库 |
| 知识管理 | 分类/专题/有效期全生命周期治理，到期检测、上下架、统计全景 |
| 中台 | 三服务分层（collector / qa_api / model_server）+ 双端复用同一知识底座 |
| 面向校务管理 | 六大专题域（新生入学/港澳生服务/教务学籍/后勤生活/就业创业/科研学术），权威来源引用 |

## 架构

```
┌───────────┐   ┌─────────────────────┐   ┌───────────┐
│ 管理端 /admin│──▶│ collector :8002      │──▶│ Milvus    │ 混合检索库
│ 问答端 /     │   │  采集调度→解析→打标→入库 │   │ MongoDB   │ 源/任务/文档元数据
└───────────┘   └─────────────────────┘   │ MinIO     │ 原文对象存储
        │                │                 └───────────┘
        └──────▶ qa_api :8003 ◀─────────────┘
                 混合检索→重排→流式生成→来源引用
                         │
                    model_server :8001
                  BGE-M3 双向量 + bge-reranker-large
```

- **collector**（知识生产）：gzhu 通知公告 + gznews 新闻网适配器、httpx+selectolax 爬取、trafilatura+LLM 兜底解析、URL/内容哈希+simhash 去重、规则+LLM 专题打标、有效期识别、幂等入库（先删后插）、APScheduler 定时调度
- **qa_api**（知识消费）：BGE-M3 dense(COSINE 0.8)+sparse(IP 0.2) 混合检索 + min-max 归一化 + 时间衰减 + 过期降权 → bge-reranker-large 重排 + 断崖截断 → DeepSeek（DashScope 备援）流式生成 → 来源引用 + 问答日志
- **model_server**（本地推理）：embedding + rerank 统一封装，权重不可用时降级不拖垮主链路
- **前端**：Vue 3 + Element Plus + echarts + markstream-vue，SSE 流式（fetch+ReadableStream 解析）

## 快速开始（一条命令起全栈）

```powershell
# 1. 复制 .env.example 为 .env，填入 BGE_M3_PATH / RERANKER_PATH / DEEPSEEK_API_KEY
# 2. 一条命令起全栈（存储 + 三后端 + 前端）
docker compose up -d --build

# 3. 播种演示数据（可选；幂等可重跑）
uv run python -m scripts.seed_demo

# 4. 打开 http://localhost:5173（问答端）；管理端 http://localhost:5173/admin
```

本地开发（不用容器）仍支持：三个终端分别 `uv run uvicorn model_server.main:app --port 8001` / `collector.main:app --port 8002` / `qa_api.main:app --port 8003`，前端 `cd frontend && pnpm dev`。

## 功能清单

**管理端（/admin）**
- 采集源管理：增删采集源、立即采集、启停
- 采集任务：状态监控、失败详情、30s 自动刷新
- 知识库管理：分类/状态/专题筛选、分页、上下架、到期检测、点标题查看详情（元数据+正文）
- 资产全景：指标卡、分类/状态/专题图表、近期任务、热门问题
- 人工数据入库（规划中）：手动录入 + 上传文件（PDF/Word/文本），编辑/删除治理，见 spec

**问答端（/）**
- 自然语言提问，SSE 流式回答，Markdown 渲染
- 每条答案附来源引用卡片（标题可点击、分类/日期、过期预警）
- 专题域筛选、示例问题、自动滚底
- 无来源时诚实回答（不编造）

## 验收状态（2026-08-19 实测）

- 后端：**55 passed**（pytest 全量，含 mock 站点真跑集成 + 真实 LLM 生成段；注入 `DEEPSEEK_API_KEY` 后无 skip）
- 前端：build ✅ + **11 passed**（vitest，含 SSE CRLF 解析器、问答端组件与知识库详情组件测试）
- 演示问题清单：**20 题逐题实测，来源引用率 20/20 = 100%**
- 空环境复现：一条 `docker compose up -d --build` 起全栈（nginx 双端代理 + SPA fallback 实测）
- 端到端：gzhu 通知公告 8 篇 + gznews 头条关注 11 篇真实采集（含 4 篇单页失败隔离）；18 篇模拟数据幂等播种；问答 SSE 全链路（chunk→sources→done）

## 目录结构

```
collector/    采集服务（crawler/parser/dedup/tagger/ingest/lifecycle/scheduler/api）
qa_api/       问答服务（retriever/reranker/generator/api）
model_server/ 本地模型推理服务
shared/       跨服务复用件（配置/客户端单例/异常/重试/日志）
frontend/     Vue3 双端前端（views/chat 问答端 + views/admin 管理端）
docs/         规格/ADR/实现计划/进度交接
tests/        后端 pytest 测试
```

## 文档索引

| 文档 | 说明 |
|------|------|
| `docs/superpowers/specs/2026-08-18-school-knowledge-hub-design.md` | 需求与设计唯一真相 |
| `docs/superpowers/specs/2026-08-20-manual-data-ingestion-design.md` | 人工数据入库设计（录入/上传/编辑/删除，规划中） |
| `docs/adr/ADR-001..011` | 技术决策记录（含模型分工与派活约定） |
| `docs/superpowers/plans/` | 后端核心（Plan 1）与前端（Plan 2）实现计划 |
| `docs/PROGRESS.md` | 跨会话进度交接（必读） |
| `docs/作品说明书.md` | 作品交付说明书（定位/创新点/架构/验收） |
| `docs/演示视频脚本.md` | 8 镜 5 分钟路演脚本 |
| `docs/demo/20-questions.md` | 演示问题清单（20 题） |
| `AGENTS.md` | 开发公约（AI 代理强制约束） |
