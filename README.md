# 校务知识中台（School Knowledge Hub）

> 面向校务管理的 AI 自动数据采集与知识管理中台

自动采集广州大学多源校务信息（通知公告、新闻网）构建知识库，师生用自然语言提问即可获得**100% 附来源引用**的可信答案。双端形态：**管理端**（采集治理 + 人工入库）+ **问答端**（自然语言问答）。

## 四大主题要素

| 要素 | 落点 |
|------|------|
| AI 自动数据采集 | 定时调度 + 站点适配器 + 爬取引擎 + 增量去重 + LLM 兜底解析 + 专题打标，全自动入库 |
| 知识管理 | 分类/专题/有效期全生命周期治理，到期检测、上下架、统计全景、人工录入/上传/编辑/删除 |
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

- **collector**（知识生产）：gzhu 通知公告 + gznews 新闻网适配器、httpx+selectolax 爬取、trafilatura+LLM 兜底解析、URL/内容哈希+simhash 去重、规则+LLM 专题打标、有效期识别、幂等入库（先删后插）、人工入库（录入/上传/编辑/删除）、APScheduler 定时调度
- **qa_api**（知识消费）：BGE-M3 dense(COSINE 0.8)+sparse(IP 0.2) 混合检索 + min-max 归一化 + 时间衰减 + 过期降权 → bge-reranker-large 重排 + 断崖截断 → DeepSeek（DashScope 备援）流式生成 → 来源引用 + 问答日志
- **model_server**（本地推理）：embedding + rerank 统一封装，权重不可用时降级不拖垮主链路
- **前端**：Vue 3 + Element Plus + echarts + markstream-vue，SSE 流式（fetch+ReadableStream 解析），nginx 双端反代

## 环境要求

| 项 | 要求 |
|----|------|
| Docker | Docker Desktop（含 Compose v2），Windows / macOS / Linux 均可 |
| 本地模型权重 | BGE-M3（embedding）+ bge-reranker-large（重排），需提前下载到本机 |
| LLM Key | DeepSeek API Key（问答生成）；DashScope Key 可选（备援） |
| 端口（需空闲） | `5173` 前端 · `8001` 模型 · `8002` 采集 · `8003` 问答 · `19530` Milvus · `27017` Mongo · `9000/9001` MinIO |

## 部署指南（一条命令起全栈）

### 第 1 步：准备模型权重

下载两个模型到本机（任选一种方式，国内推荐 ModelScope）：

**方式 A：ModelScope（国内快，推荐）**

```powershell
pip install modelscope
modelscope download --model BAAI/bge-m3 --local_dir D:/ai_models/bge-m3
modelscope download --model BAAI/bge-reranker-large --local_dir D:/ai_models/bge-reranker-large
```

**方式 B：HuggingFace + 国内镜像**

```powershell
pip install -U "huggingface_hub[cli]"
$env:HF_ENDPOINT="https://hf-mirror.com"
huggingface-cli download BAAI/bge-m3 --local-dir D:/ai_models/bge-m3
huggingface-cli download BAAI/bge-reranker-large --local-dir D:/ai_models/bge-reranker-large
```

记下两个目录的**宿主机绝对路径**（第 2 步填入 `BGE_M3_LOCAL` / `RERANKER_LOCAL`）：上例中 BGE-M3 为 `D:/ai_models/bge-m3`、重排为 `D:/ai_models/bge-reranker-large`。

### 第 2 步：配置环境变量

```powershell
# 复制配置模板
copy .env.example .env
```

编辑 `.env`，填必填项：

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | 问答生成的 DeepSeek Key（写进 `.env`，`docker compose up` 即自动带上） |
| `BGE_M3_LOCAL` | ✅ | **宿主机** BGE-M3 权重目录绝对路径（compose 挂载用，改为第 1 步下载的目录） |
| `RERANKER_LOCAL` | ✅ | **宿主机** bge-reranker-large 权重目录绝对路径（同上） |
| `DASHSCOPE_API_KEY` | ⬜ | 备援 LLM Key，可留空 |

> ⚠️ **注意路径命名**：`.env.example` 里的 `BGE_M3_PATH`/`RERANKER_PATH` 是**容器内**固定路径（`/models/...`，勿改）；宿主机路径由 `BGE_M3_LOCAL`/`RERANKER_LOCAL` 指定（`.env.example` 已含这两项，改成你的实际路径即可）。也可直接改 `docker-compose.yml` 里 model-server 的 `volumes` 默认值。

> 💡 **配置说明**：所有配置项（存储地址、模型路径、API Key、检索参数、端口、超时）都在 `.env` 里改——`shared/config.py` 全部通过 `os.getenv` 读取，`docker-compose.yml` 也引用 `.env` 变量。`.env` 已加入 `.gitignore`，不会进 git；仓库只提交 `.env.example` 模板，复制 `copy .env.example .env` 后改值即可。

### 第 3 步：启动

```powershell
docker compose up -d --build
```

首次会构建 3 个后端镜像 + 前端镜像（国内网络已内置清华 pip / npmmirror 加速）。

### 第 4 步：验证部署

```powershell
docker compose ps                      # 8 个容器均 Up
curl http://localhost:5173/            # 问答端（返回 HTML）
curl http://localhost:5173/admin       # 管理端
curl http://localhost:5173/admin-api/api/health    # 采集服务 {"status":"ok"}
curl http://localhost:5173/qa-api/api/health       # 问答服务 {"status":"ok"}
```

### 第 5 步：初始化知识数据（三选一或都做）

**方式 A — 播种演示数据**（18 篇六大专题域模拟文档，幂等可重跑；需本机 uv + Python 环境，且 `.env` 存储地址为 `localhost`）：

```powershell
uv run python -m scripts.seed_demo
```

**方式 B — 采集真实校务**（网页操作，无需代码）：

1. 打开管理端 `http://localhost:5173/admin` →「采集源管理」
2. 「新增采集源」：填 gzhu 通知公告 / gznews 新闻网的源 URL（见下），保存
3. 点「立即采集」，等任务完成后文档入库

**方式 C — 人工录入/上传**（网页操作）：管理端「知识库管理」→「新增知识」→ 手动录入或上传文件（详见下方使用指南）。

> 纯 Docker 部署者建议用方式 B/C 快速上手；方式 A 适合演示前快速铺满知识库。

## 使用指南

### 问答端（`http://localhost:5173/`）

1. 在输入框用自然语言提问（如「2026 级新生什么时候报到？」「校园卡丢了怎么补办？」）
2. 答案以 SSE 流式输出，**每条答案下方附来源引用卡片**（标题可点击、分类/日期、过期预警）
3. 可用「专题域」下拉筛选某类问题；点示例问题快速体验
4. 知识库无相关内容时**诚实回答「未找到」并给出建议，绝不编造**

### 管理端（`http://localhost:5173/admin`）

| 页面 | 用途 |
|------|------|
| 采集源管理 | 增删采集源、立即采集、启停 |
| 采集任务 | 采集状态监控、失败详情、30s 自动刷新 |
| 知识库管理 | 分类/状态/专题筛选、分页、上下架、到期检测、点标题查看详情、**新增知识** |
| 资产全景 | 指标卡、分类/状态/专题图表、近期任务、热门问题 |

### 人工数据入库（知识库管理页）

1. 点页头「**新增知识**」按钮，弹出表单
2. 正文来源二选一：
   - **手动录入**：直接粘贴/输入正文
   - **上传文件**：选 PDF / Word(.docx) / 纯文本 / Markdown，系统自动解析标题+正文回填，校对后保存
3. 字段说明：标题（必填）、正文（必填）、发布日期（默认今天）、分类/专题（**不选则系统按规则自动打标**）、来源 URL / 发布部门（可选）
4. 点「保存」→ 入库，**立即可在问答端被检索引用**
5. 点列表中标题查看详情，详情抽屉内可「**编辑**」（改后幂等覆盖）或「**删除**」（清三处存储）

## 配置项说明

完整配置见 `.env.example`（已分块注释）。关键项：

| 分组 | 变量 | 默认 | 说明 |
|------|------|------|------|
| 存储 | `MILVUS_URI` | `http://localhost:19530` | 容器内自动覆盖为 `http://milvus:19530` |
| 存储 | `MONGO_URI` | `mongodb://localhost:27017` | 同上 |
| 存储 | `MINIO_ENDPOINT` | `localhost:9000` | 同上 |
| LLM | `DEEPSEEK_MODEL` | `deepseek-chat` | 主 LLM |
| LLM | `DASHSCOPE_MODEL` | `qwen-plus` | 备援 LLM |
| 检索 | `DENSE_WEIGHT` / `SPARSE_WEIGHT` | `0.8` / `0.2` | 混合检索权重 |
| 检索 | `RECALL_TOP_K` | `10` | 召回数 |
| 超时 | `EXTERNAL_TIMEOUT` / `LLM_TIMEOUT` | `10` / `30` | 外部服务 / LLM 超时（秒） |

## 常见问题（FAQ）

- **第一次问答返回「未找到」/空回复？** model-server 冷启动加载 BGE-M3 需约 30–90s，第一次提问可能因超时未召回。等约 1 分钟再问，或先 `curl -X POST http://localhost:8001/embed -H "Content-Type: application/json" -d "{\"texts\":[\"预热\"]}"` 预热一次。
- **`docker compose up` 后容器里没有 DeepSeek Key？** 确保 `.env` 文件里 `DEEPSEEK_API_KEY=sk-...` 已填（compose 通过 `env_file` 读取）。
- **model-server 起不来 / 一直重启？** 检查 `BGE_M3_LOCAL`、`RERANKER_LOCAL` 是否指向真实存在的权重目录。
- **端口被占用？** 见「环境要求」端口清单；改 `docker-compose.yml` 的 `ports` 映射后重启。
- **Windows 上 localhost 连不上存储？** 可能是 IPv6 歧义，改用 `127.0.0.1`；若本机 WSL2 也在跑 Docker，`127.0.0.1` 可能被 WSL 中继抢占（关掉 WSL 或改端口）。

## 本地开发（不用容器）

三个终端分别启动后端：

```powershell
uv run uvicorn model_server.main:app --port 8001
uv run uvicorn collector.main:app  --port 8002
uv run uvicorn qa_api.main:app     --port 8003
```

前端：`cd frontend && pnpm dev`（默认 5173，含代理）。运行测试：`uv run pytest tests/`（后端）、`cd frontend && pnpm exec vitest run`（前端）。

## 功能清单

**管理端（/admin）**
- 采集源管理：增删采集源、立即采集、启停、采集页数控制（1/3/5/10/全部，全部封顶 50 页）
- 采集任务：状态监控、失败详情、30s 自动刷新
- 知识库管理：分类/状态/专题筛选、分页、上下架、到期检测、点标题查看详情（元数据+正文）
- 资产全景：指标卡、分类/状态/专题图表、近期任务、热门问题
- 人工数据入库：手动录入 + 上传文件（PDF/Word/文本），编辑/删除治理

**问答端（/）**
- 自然语言提问，SSE 流式回答，Markdown 渲染
- 每条答案附来源引用卡片（标题可点击、分类/日期、过期预警）
- 专题域筛选、示例问题、自动滚底
- 无来源时诚实回答（不编造）
- 多轮会话：历史会话持久化（MongoDB）、左侧边栏查看/切换/删除、新会话（豆包式）

## 验收状态（2026-08-20 实测）

- 后端：**101 passed**（pytest 全量，含 mock 站点真跑集成 + 真实 LLM 生成段 + 人工入库 + 多轮会话 + 采集页数控制器；注入 `DEEPSEEK_API_KEY` 后无 skip）
- 前端：build ✅ + **34 passed**（vitest，含 SSE CRLF 解析器、问答端组件、知识库详情、人工入库表单、会话侧边栏与采集源采集页数组件测试）
- 演示问题清单：**20 题逐题实测，来源引用率 20/20 = 100%**
- 空环境复现：一条 `docker compose up -d --build` 起全栈（nginx 双端代理 + SPA fallback 实测）
- 端到端：gzhu 通知公告 8 篇 + gznews 头条关注 11 篇真实采集（含 4 篇单页失败隔离）；18 篇模拟数据幂等播种；人工入库（录入/编辑/上传/删除）真跑通过；问答 SSE 全链路（chunk→sources→done）；多轮会话（新建/切换/删除/刷新不丢）真跑通过

## 目录结构

```
collector/    采集服务（crawler/parser/dedup/tagger/ingest/lifecycle/scheduler/api）
qa_api/       问答服务（retriever/reranker/generator/api）
model_server/ 本地模型推理服务
shared/       跨服务复用件（配置/客户端单例/异常/重试/日志）
frontend/     Vue3 双端前端（views/chat 问答端 + views/admin 管理端）
docs/         规格/ADR/实现计划/进度交接
tests/        后端 pytest 测试
scripts/      播种/演示等脚本
```

## 文档索引

| 文档 | 说明 |
|------|------|
| `docs/superpowers/specs/2026-08-18-school-knowledge-hub-design.md` | 需求与设计唯一真相 |
| `docs/superpowers/specs/2026-08-20-manual-data-ingestion-design.md` | 人工数据入库设计（录入/上传/编辑/删除） |
| `docs/adr/ADR-001..011` | 技术决策记录（含模型分工与派活约定） |
| `docs/superpowers/plans/` | 后端核心（Plan 1）、前端（Plan 2）、交付（Plan 3）、人工入库（Plan 4）实现计划 |
| `docs/PROGRESS.md` | 跨会话进度交接（必读） |
| `docs/作品说明书.md` | 作品交付说明书（定位/创新点/架构/验收） |
| `docs/演示视频脚本.md` | 8 镜 5 分钟路演脚本 |
| `docs/demo/20-questions.md` | 演示问题清单（20 题） |
| `AGENTS.md` | 开发公约（AI 代理强制约束） |
