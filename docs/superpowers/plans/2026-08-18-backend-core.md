# 后端核心 Implementation Plan（shared / model_server / collector / qa_api）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **派活约定（ADR-011）**：本计划任务由主会话（deepseek-v4-pro）用 `workflow` 按阶段批量派发给 `model: 'glm-5.3'` 执行；任务简报必须自包含（本计划的 Task 章节即简报，含文件/接口/验收/测试代码）。主会话自己执行脚手架任务（A1~A3）。

**Goal:** 实现校务 AI 中台的后端核心：本地模型服务、多源自动采集管道（含知识管理）、可信问答链路（混合检索+重排+流式生成）。

**Architecture:** 三服务分层——`model_server`（FlagEmbedding FastAPI：BGE-M3 双向量 + bge-reranker-large）、`collector`（APScheduler 调度采集→解析→打标→时效→三写入库，含知识生命周期与管理端 API）、`qa_api`（Milvus 混合检索+时间衰减→rerank→DeepSeek/DashScope 流式生成，SSE 输出附来源引用）。服务间只通过 HTTP API 与共享存储（Milvus/MongoDB/MinIO）通信。

**Tech Stack:** Python 3.11+、uv、FastAPI、pymilvus 2.4+、motor（异步 MongoDB）、minio、httpx、selectolax、trafilatura、APScheduler、FlagEmbedding（BGE-M3、bge-reranker-large）、openai SDK（DeepSeek/DashScope OpenAI 兼容）、sse-starlette、pytest/pytest-asyncio。

**Spec:** `docs/superpowers/specs/2026-08-18-school-knowledge-hub-design.md`（执行者必读）

## Global Constraints

- 服务间不互相调用业务逻辑，只通过 HTTP API 与共享存储通信（spec 第 4 节）。
- 降级铁律：可选依赖失败不得拖垮主链路——reranker 挂→跳过精排；sparse 异常→仅 dense；MinIO 挂→跳过快照标记缺失；MongoDB 挂→日志降级文件；LLM 主挂→切 DashScope（spec 第 8 节）。
- 检索参数：dense COSINE 0.8 + sparse IP 0.2 + norm_score 归一化；召回 top_k=10；时间衰减指数 `0.5 ** (days/30)`（半衰期 30 天）；过期文档再乘 0.25 并打标；断崖截断 ratio=0.3（spec 第 6.2 节、ADR-006）。
- 幂等入库：入库前查重（URL+内容哈希），同一任务重复跑不产生重复数据（spec 第 8 节）。
- 密钥纪律：`.env` 不进 git、`.env.example` 进 git、绝不硬编码密钥（ADR-007）。
- 模型权重本地挂载路径（ADR-005）：BGE-M3=`D:\ai_models\huggingface_cache\bge-m3\models\BAAI--bge-m3\snapshots\master`、reranker=`D:\ai_models\modelscope_cache\models\BAAI--bge-reranker-large\snapshots\master`；容器挂载 `/models/bge-m3`、`/models/bge-reranker-large`。
- 所有外部调用统一超时（默认 10s，可配）；LLM 30s。
- 横切关注点（日志/异常/重试）收敛在 `shared/` 基类，业务层只写业务。
- YAGNI：不做 RAGAS 评测、登录权限、多租户、附件问答、长期对话记忆（spec 第 11 节）。
- 中文：日志/注释/提示词/提交信息均用中文。

## File Structure（本计划创建的文件）

```
pyproject.toml                    # uv 项目定义 + 全部依赖
.env.example                      # 配置样例（进 git）
.gitignore                        # 追加 .env、__pycache__ 等
shared/
├── __init__.py
├── config.py                     # Settings dataclass（读 .env）
├── clients.py                    # Milvus/Mongo/MinIO/LLM 客户端单例
├── errors.py                     # 异常基类体系
├── retry.py                      # 指数退避装饰器
└── logging.py                    # 结构化日志（task_id/request_id 上下文）
model_server/
├── __init__.py
├── main.py                       # FastAPI：/embed /rerank /health
├── models.py                     # FlagEmbedding 模型加载（BGE-M3 + reranker）
└── Dockerfile
collector/
├── __init__.py
├── main.py                       # FastAPI 应用装配 + 管理端路由
├── config.py                     # 采集源/调度默认配置
├── scheduler.py                  # APScheduler 装配
├── tasks.py                      # 采集任务状态机 + 重试
├── crawler/
│   ├── __init__.py
│   ├── base.py                   # SiteAdapter 基类 + ArticleRef/RawArticle 模型
│   ├── gzhu.py                   # 广州大学主站适配器
│   ├── gznews.py                 # 广州大学新闻网适配器
│   └── engine.py                 # httpx 抓取引擎 + 去重
├── parser/
│   ├── __init__.py
│   └── extract.py                # trafilatura 提取 + 元数据 + LLM 兜底
├── tagger/
│   ├── __init__.py
│   ├── rules.py                  # 一级分类规则
│   └── llm_topics.py             # 专题域 LLM 批量打标
├── lifecycle/
│   ├── __init__.py
│   └── validity.py               # 时效推断 + 过期判定
├── ingest/
│   ├── __init__.py
│   ├── splitter.py               # 文本切分
│   └── writer.py                 # 向量化 + Milvus/Mongo/MinIO 三写
├── knowledge.py                  # 知识库管理（列表/筛选/上下架/统计）
├── api/
│   ├── __init__.py
│   ├── sources.py                # 采集源 CRUD
│   ├── tasks.py                  # 任务触发/状态查询
│   └── knowledge.py              # 知识库管理 API
qa_api/
├── __init__.py
├── main.py                       # FastAPI 应用装配
├── retriever/
│   ├── __init__.py
│   └── hybrid.py                 # 混合检索+过滤+时间衰减+过期降权
├── reranker/
│   ├── __init__.py
│   └── rerank.py                 # 精排 + 断崖截断
├── generator/
│   ├── __init__.py
│   ├── llm.py                    # LLM 主备降级 + 流式
│   └── prompts.py                # 提示词模板（中文）
└── api/
    ├── __init__.py
    └── chat.py                   # /chat SSE + 来源引用 + 问答日志
tests/
├── conftest.py                   # fixture（mock 客户端/样例 HTML）
├── test_parser.py
├── test_dedup.py
├── test_tagger.py
├── test_validity.py
├── test_splitter.py
├── test_hybrid.py
├── test_rerank.py
├── test_llm_fallback.py
└── test_ingest_idempotent.py
docker-compose.yml                # milvus/etcd/minio/mongo + 三服务（骨架，本计划搭好存储部分）
```

## 阶段 A：骨架与基础设施（主会话直接执行，不派发）

### Task A1: Python 项目骨架 + 全局配置

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `.gitignore`（创建）

**Interfaces:**
- Produces: `shared.config.Settings` dataclass 与 `settings` 单例（Task A2 及之后所有任务使用）

- [ ] **Step 1: 创建 pyproject.toml（uv 管理，单项目多入口）**

```toml
[project]
name = "school-knowledge-hub"
version = "0.1.0"
description = "面向校务管理的AI自动数据采集与知识管理中台"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sse-starlette>=2.1",
    "pymilvus>=2.4.0",
    "motor>=3.5",
    "minio>=7.2",
    "httpx>=0.27",
    "selectolax>=0.3",
    "trafilatura>=2.0",
    "apscheduler>=3.10",
    "openai>=1.40",
    "pydantic>=2.8",
    "pydantic-settings>=2.4",
    "python-dotenv>=1.0",
    "FlagEmbedding>=1.2.10",
    "simhash>=2.1",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.uv]
package = false
```

- [ ] **Step 2: 创建 .env.example（全部可配项，注释中文说明）**

```ini
# ===== 存储（Docker Compose 编排） =====
MILVUS_URI=http://localhost:19530
MONGO_URI=mongodb://localhost:27017
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=school-knowledge-hub
MINIO_SECURE=false

# ===== LLM（主备） =====
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-plus

# ===== 本地模型服务 =====
EMBED_SERVICE_URL=http://model-server:8001
RERANK_SERVICE_URL=http://model-server:8001
BGE_M3_PATH=/models/bge-m3
RERANKER_PATH=/models/bge-reranker-large

# ===== Milvus 集合 =====
MILVUS_COLLECTION=school_docs

# ===== 检索参数（ADR-006） =====
DENSE_WEIGHT=0.8
SPARSE_WEIGHT=0.2
RECALL_TOP_K=10
TIME_DECAY_HALF_LIFE_DAYS=30
EXPIRED_PENALTY=0.25
CLIFF_CUTOFF_RATIO=0.3

# ===== 服务端口 =====
COLLECTOR_PORT=8002
QA_API_PORT=8003
```

- [ ] **Step 3: 创建 .gitignore（追加到仓库根）**

```gitignore
.env
__pycache__/
*.pyc
.pytest_cache/
.venv/
node_modules/
dist/
```

- [ ] **Step 4: 创建 shared/config.py（Settings dataclass，dotenv 注入）**

```python
"""全局配置：.env → dataclass 单例。"""
from dataclasses import dataclass, field
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # 存储
    milvus_uri: str = os.getenv("MILVUS_URI", "http://localhost:19530")
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "school-knowledge-hub")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    # LLM
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    dashscope_model: str = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
    # 模型服务
    embed_service_url: str = os.getenv("EMBED_SERVICE_URL", "http://localhost:8001")
    rerank_service_url: str = os.getenv("RERANK_SERVICE_URL", "http://localhost:8001")
    bge_m3_path: str = os.getenv("BGE_M3_PATH", "/models/bge-m3")
    reranker_path: str = os.getenv("RERANKER_PATH", "/models/bge-reranker-large")
    # Milvus
    milvus_collection: str = os.getenv("MILVUS_COLLECTION", "school_docs")
    # 检索参数（ADR-006）
    dense_weight: float = float(os.getenv("DENSE_WEIGHT", "0.8"))
    sparse_weight: float = float(os.getenv("SPARSE_WEIGHT", "0.2"))
    recall_top_k: int = int(os.getenv("RECALL_TOP_K", "10"))
    time_decay_half_life_days: float = float(os.getenv("TIME_DECAY_HALF_LIFE_DAYS", "30"))
    expired_penalty: float = float(os.getenv("EXPIRED_PENALTY", "0.25"))
    cliff_cutoff_ratio: float = float(os.getenv("CLIFF_CUTOFF_RATIO", "0.3"))
    # 端口
    collector_port: int = int(os.getenv("COLLECTOR_PORT", "8002"))
    qa_api_port: int = int(os.getenv("QA_API_PORT", "8003"))
    # 通用
    external_timeout: float = float(os.getenv("EXTERNAL_TIMEOUT", "10"))
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "30"))


settings = Settings()
```

- [ ] **Step 5: 验证与提交**

Run: `uv run python -c "from shared.config import settings; print(settings.milvus_uri)"`
Expected: 打印 `http://localhost:19530`

```bash
git add pyproject.toml .env.example .gitignore shared/
git commit -m "feat: 项目骨架与全局配置(uv+Settings)"
```

### Task A2: shared 基础设施（客户端单例/异常/重试/日志）

**Files:**
- Create: `shared/errors.py`
- Create: `shared/retry.py`
- Create: `shared/logging.py`
- Create: `shared/clients.py`

**Interfaces:**
- Produces:
  - `shared.errors.AppError(Exception)`、`ExternalServiceError(AppError)`、`DegradedError(AppError)`、`ValidationError(AppError)`
  - `shared.retry.async_retry(retries=3, base_delay=1.0, max_delay=10.0)` 装饰器（指数退避，只重试 ExternalServiceError）
  - `shared.logging.get_logger(name)` 返回带上下文 task_id/request_id 的结构化 logger
  - `shared.clients.get_milvus() -> pymilvus.MilvusClient`（单例）
  - `shared.clients.get_mongo() -> motor.motor_asyncio.AsyncIOMotorDatabase`（单例，返回 db）
  - `shared.clients.get_minio() -> minio.Minio`（单例）
  - `shared.clients.get_llm() -> openai.AsyncOpenAI`（主 DeepSeek 单例）
  - `shared.clients.get_llm_backup() -> openai.AsyncOpenAI`（备 DashScope 单例）

- [ ] **Step 1: 写失败测试 tests/test_shared.py**

```python
import pytest
from shared.errors import ExternalServiceError
from shared.retry import async_retry


async def test_retry_then_success():
    calls = []

    @async_retry(retries=3, base_delay=0.01, max_delay=0.01)
    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ExternalServiceError("挂了")
        return "ok"

    assert await flaky() == "ok"
    assert len(calls) == 3


async def test_retry_exhausted():
    @async_retry(retries=2, base_delay=0.01, max_delay=0.01)
    async def always_fail():
        raise ExternalServiceError("一直挂")

    with pytest.raises(ExternalServiceError):
        await always_fail()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_shared.py -v`
Expected: FAIL（`ModuleNotFoundError: shared.retry`）

- [ ] **Step 3: 实现 shared/errors.py**

```python
"""异常基类体系：业务层只抛业务异常。"""


class AppError(Exception):
    """应用异常基类。"""


class ExternalServiceError(AppError):
    """外部服务（Milvus/Mongo/MinIO/LLM/模型服务）调用失败。"""


class DegradedError(AppError):
    """可选依赖降级后仍无法满足请求（用于告警标记）。"""


class ValidationError(AppError):
    """输入/配置校验失败。"""
```

- [ ] **Step 4: 实现 shared/retry.py**

```python
"""指数退避重试装饰器（只重试外部服务错误）。"""
import asyncio
import functools

from shared.errors import ExternalServiceError


def async_retry(retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
    def deco(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except ExternalServiceError:
                    if attempt == retries - 1:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    await asyncio.sleep(delay)
        return wrapper
    return deco
```

- [ ] **Step 5: 实现 shared/logging.py**

```python
"""结构化日志：任务/请求 ID 贯穿。"""
import contextvars
import logging
import sys

_task_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("task_id", default=None)
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


class CtxFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.task_id = _task_id.get() or "-"
        record.request_id = _request_id.get() or "-"
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s [task=%(task_id)s req=%(request_id)s] %(message)s"))
        handler.addFilter(CtxFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
```

- [ ] **Step 6: 实现 shared/clients.py（全部单例）**

```python
"""昂贵资源客户端单例（Milvus/Mongo/MinIO/LLM 主备）。"""
from functools import lru_cache

from minio import Minio
from motor.motor_asyncio import AsyncIOMotorClient
from openai import AsyncOpenAI
from pymilvus import MilvusClient

from shared.config import settings


@lru_cache(maxsize=1)
def get_milvus() -> MilvusClient:
    return MilvusClient(uri=settings.milvus_uri)


@lru_cache(maxsize=1)
def get_mongo() -> AsyncIOMotorDatabase:
    client = AsyncIOMotorClient(settings.mongo_uri)
    return client["school_knowledge_hub"]


@lru_cache(maxsize=1)
def get_minio() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


@lru_cache(maxsize=1)
def get_llm() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


@lru_cache(maxsize=1)
def get_llm_backup() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)
```

- [ ] **Step 7: 运行测试通过并提交**

Run: `uv run pytest tests/test_shared.py -v`
Expected: PASS（2 passed）

```bash
git add shared/ tests/test_shared.py
git commit -m "feat: shared基础设施(单例/异常/重试/日志)"
```

### Task A3: model_server 本地模型服务

**Files:**
- Create: `model_server/__init__.py`
- Create: `model_server/models.py`
- Create: `model_server/main.py`
- Create: `model_server/Dockerfile`

**Interfaces:**
- Produces（HTTP，qa_api/collector 依赖）:
  - `POST /embed` body `{"texts": ["..."]}` → `{"embeddings": [{"dense": [1024 个 float], "sparse": {"<int token_id>": <float>}}]}`
  - `POST /rerank` body `{"query": "...", "documents": ["..."]}` → `{"scores": [float], "order": [int]}`
  - `GET /health` → `{"status": "ok"}`

- [ ] **Step 1: 实现 model_server/models.py（模型懒加载单例）**

```python
"""FlagEmbedding 模型加载：BGE-M3（dense+sparse）与 bge-reranker-large。"""
from functools import lru_cache

from FlagEmbedding import BGEM3FlagModel, FlagReranker

from shared.config import settings


@lru_cache(maxsize=1)
def get_bge_m3() -> BGEM3FlagModel:
    return BGEM3FlagModel(settings.bge_m3_path, use_fp16=True)


@lru_cache(maxsize=1)
def get_reranker() -> FlagReranker:
    return FlagReranker(settings.reranker_path, use_fp16=True)
```

- [ ] **Step 2: 实现 model_server/main.py**

```python
"""本地模型服务：BGE-M3 双向量 + bge-reranker-large 重排。"""
from fastapi import FastAPI
from pydantic import BaseModel

from model_server.models import get_bge_m3, get_reranker
from shared.logging import get_logger

logger = get_logger("model_server")
app = FastAPI(title="校务中台·本地模型服务")


class EmbedRequest(BaseModel):
    texts: list[str]


class RerankRequest(BaseModel):
    query: str
    documents: list[str]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/embed")
async def embed(req: EmbedRequest):
    model = get_bge_m3()
    out = model.encode(req.texts, return_dense=True, return_sparse=True)
    embeddings = [
        {"dense": list(d), "sparse": {int(k): float(v) for k, v in s.items()}}
        for d, s in zip(out["dense_vecs"], out["lexical_weights"])
    ]
    return {"embeddings": embeddings}


@app.post("/rerank")
async def rerank(req: RerankRequest):
    model = get_reranker()
    pairs = [[req.query, doc] for doc in req.documents]
    scores = model.compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        scores = [scores]
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    return {"scores": [float(s) for s in scores], "order": order}
```

- [ ] **Step 3: 实现 model_server/Dockerfile（挂载本地权重）**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY shared ./shared
COPY model_server ./model_server
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" FlagEmbedding pydantic python-dotenv
ENV BGE_M3_PATH=/models/bge-m3
ENV RERANKER_PATH=/models/bge-reranker-large
EXPOSE 8001
CMD ["uvicorn", "model_server.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 4: 本地冒烟验证（本机直跑，非容器）**

Run: `uv run uvicorn model_server.main:app --port 8001` 后另开终端：
`curl -s http://localhost:8001/health`
Expected: `{"status":"ok"}`
（embed/rerank 首次调用会加载模型，BGE-M3 约 2GB，属预期）

- [ ] **Step 5: 提交**

```bash
git add model_server/
git commit -m "feat: model_server本地模型服务(BGE-M3双向量+bge-reranker-large)"
```

### Task A4: docker-compose 存储编排骨架

**Files:**
- Create: `docker-compose.yml`

**Interfaces:**
- Produces: 存储服务（milvus/etcd/minio/mongo）+ 三个服务占位（collector/qa-api 的 Dockerfile 在 B8/C4 补齐，model-server 已就绪）

- [ ] **Step 1: 创建 docker-compose.yml**

```yaml
services:
  etcd:
    image: quay.io/coreos/etcd:v3.5.14
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
    command: etcd -advertise-client-urls=http://etcd:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd
    volumes:
      - etcd_data:/etcd
  minio:
    image: minio/minio:latest
    command: minio server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-minioadmin}
    ports: ["9000:9000", "9001:9001"]
    volumes:
      - minio_data:/data
  milvus:
    image: milvusdb/milvus:v2.4.15
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
      MINIO_ACCESS_KEY_ID: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_SECRET_ACCESS_KEY: ${MINIO_SECRET_KEY:-minioadmin}
    ports: ["19530:19530", "9091:9091"]
    depends_on: [etcd, minio]
    volumes:
      - milvus_data:/var/lib/milvus
  mongo:
    image: mongo:7
    ports: ["27017:27017"]
    volumes:
      - mongo_data:/data/db
  model-server:
    build: ./model_server
    ports: ["8001:8001"]
    environment:
      BGE_M3_PATH: /models/bge-m3
      RERANKER_PATH: /models/bge-reranker-large
    volumes:
      - ${BGE_M3_LOCAL:-D:/ai_models/huggingface_cache/bge-m3/models/BAAI--bge-m3/snapshots/master}:/models/bge-m3
      - ${RERANKER_LOCAL:-D:/ai_models/modelscope_cache/models/BAAI--bge-reranker-large/snapshots/master}:/models/bge-reranker-large
  # collector 与 qa-api 服务在 Task B8 / C4 补 Dockerfile 后追加
volumes:
  etcd_data:
  minio_data:
  milvus_data:
  mongo_data:
```

- [ ] **Step 2: 验证存储起得来**

Run: `docker compose up -d etcd minio mongo milvus`
Expected: `docker compose ps` 四个服务 running（milvus healthy）

- [ ] **Step 3: 提交**

```bash
git add docker-compose.yml
git commit -m "feat: docker-compose存储编排(milvus/mongo/minio/etcd)"
```

---

## 阶段 B：采集管道（派发 glm-5.3 批量，Task B1~B4 一批）

### Task B1: 站点适配器（基类 + 广州大学主站/新闻网）

**Files:**
- Create: `collector/__init__.py`、`collector/crawler/__init__.py`
- Create: `collector/crawler/base.py`
- Create: `collector/crawler/gzhu.py`
- Create: `collector/crawler/gznews.py`
- Test: `tests/test_adapters.py`

**Interfaces:**
- Consumes: `shared.logging.get_logger`
- Produces:
  - `ArticleRef`（dataclass：`url: str, title: str, publish_date: str | None`）
  - `RawArticle`（dataclass：`url: str, title: str, html: str, publish_date: str | None, source_site: str, column: str`）
  - `SiteAdapter` 基类：`site: str`、`parse_list(html: str, base_url: str) -> list[ArticleRef]`、`parse_detail(html: str, ref: ArticleRef) -> RawArticle`
  - `GUZhuAdapter`（主站）、`GUNewsAdapter`（新闻网）

- [ ] **Step 1: 写失败测试 tests/test_adapters.py**

```python
from collector.crawler.base import ArticleRef
from collector.crawler.gzhu import GUZhuAdapter

LIST_HTML = """
<html><body><div class="list_news"><ul>
<li><a href="info/1087/33327.htm" title="关于给予曾玮等14名学生退学处理的预公告">关于给予曾玮等14名学生退学处理的预公告</a><span>2026-04-30</span></li>
<li><a href="info/1087/32827.htm" title="广州大学2026年高等学历继续教育专业和校外教学点拟设置情况公示">广州大学2026年高等学历继续教育专业和校外教学点拟设置情况公示</a><span>2026-04-17</span></li>
</ul></div></body></html>
"""

DETAIL_HTML = """
<html><head><title>关于给予曾玮等14名学生退学处理的预公告</title></head>
<body><div class="content">
<div class="title"><h1>关于给予曾玮等14名学生退学处理的预公告</h1></div>
<p class="date">发布时间：2026-04-30</p>
<p>来源：教务处</p>
<p>根据《广州大学学生管理规定》，现对曾玮等14名学生给予退学处理预公告。</p>
</div></body></html>
"""


def test_gzhu_parse_list():
    adapter = GUZhuAdapter()
    refs = adapter.parse_list(LIST_HTML, "https://www.gzhu.edu.cn/z__l/tzgg.htm")
    assert len(refs) == 2
    assert refs[0].title == "关于给予曾玮等14名学生退学处理的预公告"
    assert refs[0].publish_date == "2026-04-30"


def test_gzhu_parse_detail():
    adapter = GUZhuAdapter()
    ref = ArticleRef(url="https://www.gzhu.edu.cn/info/1087/33327.htm",
                     title="关于给予曾玮等14名学生退学处理的预公告", publish_date="2026-04-30")
    raw = adapter.parse_detail(DETAIL_HTML, ref)
    assert raw.url == ref.url
    assert raw.column == "通知公告"
    assert raw.source_site == "gzhu"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_adapters.py -v`
Expected: FAIL（`ModuleNotFoundError: collector.crawler.gzhu`）

- [ ] **Step 3: 实现 collector/crawler/base.py**

```python
"""站点适配器基类与文章数据模型。"""
from dataclasses import dataclass

from selectolax.parser import HTMLParser


@dataclass
class ArticleRef:
    """列表页条目引用。"""
    url: str
    title: str
    publish_date: str | None = None


@dataclass
class RawArticle:
    """详情页抓取的原始文章。"""
    url: str
    title: str
    html: str
    publish_date: str | None
    source_site: str
    column: str


class SiteAdapter:
    """站点适配器基类：列表页解析 + 详情页解析。"""

    site: str = ""

    def parse_list(self, html: str, base_url: str) -> list[ArticleRef]:
        raise NotImplementedError

    def parse_detail(self, html: str, ref: ArticleRef) -> RawArticle:
        raise NotImplementedError

    def _abs_url(self, base_url: str, href: str) -> str:
        if href.startswith("http"):
            return href
        return base_url.rsplit("/", 1)[0] + "/" + href.lstrip("./")

    def _text(self, node, default: str = "") -> str:
        return node.text(strip=True) if node is not None else default
```

- [ ] **Step 4: 实现 collector/crawler/gzhu.py**

```python
"""广州大学主站适配器（www.gzhu.edu.cn 通知公告等栏目）。"""
import re

from selectolax.parser import HTMLParser

from collector.crawler.base import ArticleRef, RawArticle, SiteAdapter


class GUZhuAdapter(SiteAdapter):
    site = "gzhu"

    def parse_list(self, html: str, base_url: str) -> list[ArticleRef]:
        tree = HTMLParser(html)
        refs: list[ArticleRef] = []
        for li in tree.css("div.list_news li, ul.news_list li, li"):
            a = li.css_first("a[href]")
            if a is None or "info/" not in (a.attributes.get("href") or ""):
                continue
            date_node = li.css_first("span")
            refs.append(ArticleRef(
                url=self._abs_url(base_url, a.attributes["href"]),
                title=a.attributes.get("title") or self._text(a),
                publish_date=self._text(date_node) if date_node else None,
            ))
        return refs

    def parse_detail(self, html: str, ref: ArticleRef) -> RawArticle:
        tree = HTMLParser(html)
        title_node = tree.css_first("h1") or tree.css_first("title")
        title = self._text(title_node, ref.title) or ref.title
        date_node = tree.css_first("p.date, .date, span.date")
        date_text = self._text(date_node) if date_node else (ref.publish_date or "")
        m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", date_text)
        return RawArticle(
            url=ref.url,
            title=title,
            html=html,
            publish_date=m.group(1) if m else ref.publish_date,
            source_site=self.site,
            column="通知公告",
        )
```

- [ ] **Step 5: 实现 collector/crawler/gznews.py**

```python
"""广州大学新闻网适配器（news.gzhu.edu.cn）。"""
import re

from selectolax.parser import HTMLParser

from collector.crawler.base import ArticleRef, RawArticle, SiteAdapter


class GUNewsAdapter(SiteAdapter):
    site = "gznews"

    def parse_list(self, html: str, base_url: str) -> list[ArticleRef]:
        tree = HTMLParser(html)
        refs: list[ArticleRef] = []
        for li in tree.css("ul li"):
            a = li.css_first("a[href]")
            if a is None or "info/" not in (a.attributes.get("href") or ""):
                continue
            date_node = li.css_first("span, .date")
            refs.append(ArticleRef(
                url=self._abs_url(base_url, a.attributes["href"]),
                title=a.attributes.get("title") or self._text(a),
                publish_date=self._text(date_node) if date_node else None,
            ))
        return refs

    def parse_detail(self, html: str, ref: ArticleRef) -> RawArticle:
        tree = HTMLParser(html)
        title_node = tree.css_first("h1") or tree.css_first("title")
        title = self._text(title_node, ref.title) or ref.title
        date_text = ref.publish_date or ""
        m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", date_text)
        return RawArticle(
            url=ref.url,
            title=title,
            html=html,
            publish_date=m.group(1) if m else ref.publish_date,
            source_site=self.site,
            column="新闻动态",
        )
```

- [ ] **Step 6: 运行测试通过并提交**

Run: `uv run pytest tests/test_adapters.py -v`
Expected: PASS（2 passed）

```bash
git add collector/ tests/test_adapters.py
git commit -m "feat: 站点适配器(广州大学主站+新闻网)"
```

### Task B2: 爬虫引擎 + 增量去重

**Files:**
- Create: `collector/dedup.py`
- Create: `collector/crawler/engine.py`
- Test: `tests/test_dedup.py`、`tests/test_engine.py`

**Interfaces:**
- Consumes: `SiteAdapter`（B1）、`shared.config.settings`、`shared.errors`
- Produces:
  - `collector.dedup.url_hash(url: str) -> str`（sha256 前 16 位）、`content_hash(html: str) -> str`（md5）
  - `collector.crawler.engine.CrawlEngine`：`async fetch_source(list_url: str, adapter: SiteAdapter) -> tuple[list[RawArticle], list[dict]]`（返回 (新文章, 失败清单)；URL+内容哈希去重；单页失败隔离；构造参数 `http_client` 供测试注入）

- [ ] **Step 1: 写失败测试 tests/test_dedup.py 与 tests/test_engine.py**

```python
import hashlib

from collector.dedup import content_hash, near_duplicate, url_hash


def test_url_hash_stable():
    assert url_hash("https://www.gzhu.edu.cn/info/1087/33327.htm") == \
        hashlib.sha256("https://www.gzhu.edu.cn/info/1087/33327.htm".encode()).hexdigest()[:16]


def test_content_hash_differs():
    assert content_hash("<html>a</html>") != content_hash("<html>b</html>")
    assert content_hash("<html>a</html>") == content_hash("<html>a</html>")


def test_near_duplicate_similar_titles():
    assert near_duplicate("关于2026年暑假放假安排的通知", "关于2026年暑假放假安排的通知（修订）")
    assert not near_duplicate("关于2026年暑假放假安排的通知", "关于研究生复试录取工作的通知")
```

```python
from collector.crawler.base import ArticleRef, RawArticle, SiteAdapter
from collector.crawler.engine import CrawlEngine


class FakeAdapter(SiteAdapter):
    site = "fake"

    def __init__(self):
        self.fail_url = None

    def parse_list(self, html, base_url):
        return [ArticleRef(url="https://x/info/1.htm", title="一", publish_date="2026-08-01"),
                ArticleRef(url="https://x/info/2.htm", title="二", publish_date="2026-08-02")]

    def parse_detail(self, html, ref):
        if ref.url == self.fail_url:
            raise RuntimeError("boom")
        return RawArticle(url=ref.url, title=ref.title, html=html,
                          publish_date=ref.publish_date, source_site="fake", column="测试")


class FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        pass


class FakeHTTP:
    def __init__(self):
        self.requests: list[str] = []

    async def get(self, url: str, **kwargs):
        self.requests.append(url)
        return FakeResponse("<html>fake list</html>" if "list" in url else "<html>fake detail</html>")


async def test_engine_fetches_and_dedups():
    adapter = FakeAdapter()
    engine = CrawlEngine(http_client=FakeHTTP())
    articles, failures = await engine.fetch_source("https://x/list.htm", adapter)
    assert len(articles) == 2
    assert failures == []
    # 第二轮：全部已见，无新文章
    articles2, _ = await engine.fetch_source("https://x/list.htm", adapter)
    assert articles2 == []


async def test_engine_isolates_page_failure():
    adapter = FakeAdapter()
    adapter.fail_url = "https://x/info/1.htm"
    engine = CrawlEngine(http_client=FakeHTTP())
    articles, failures = await engine.fetch_source("https://x/list.htm", adapter)
    assert len(articles) == 1
    assert len(failures) == 1
    assert failures[0]["url"] == "https://x/info/1.htm"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_dedup.py tests/test_engine.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 collector/dedup.py**

```python
"""增量去重：URL 哈希 + 内容哈希 + simhash 近重复检测。"""
import hashlib

from simhash import Simhash


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def content_hash(html: str) -> str:
    return hashlib.md5(html.encode()).hexdigest()


def near_duplicate(text_a: str, text_b: str, max_distance: int = 3) -> bool:
    """simhash 汉明距离判定近重复（知识治理：合并重复公告用）。"""
    return Simhash(text_a).distance(Simhash(text_b)) <= max_distance
```

- [ ] **Step 4: 实现 collector/crawler/engine.py**

```python
"""爬虫引擎：异步抓取列表页与详情页，增量去重，单页失败隔离。"""
import asyncio

import httpx

from collector.crawler.base import RawArticle, SiteAdapter
from collector.dedup import content_hash, url_hash
from shared.config import settings
from shared.errors import ExternalServiceError
from shared.logging import get_logger

logger = get_logger("collector.engine")


class CrawlEngine:
    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._http = http_client or httpx.AsyncClient(timeout=settings.external_timeout)
        self._seen: set[str] = set()

    def has_seen(self, key: str) -> bool:
        return key in self._seen

    def set_seen(self, key: str) -> None:
        self._seen.add(key)

    async def fetch_source(self, list_url: str, adapter: SiteAdapter) -> tuple[list[RawArticle], list[dict]]:
        """抓取一个列表页：返回 (新文章列表, 失败清单)。"""
        try:
            resp = await self._http.get(list_url)
            resp.raise_for_status()
        except Exception as e:
            raise ExternalServiceError(f"列表页抓取失败 {list_url}: {e}") from e
        refs = adapter.parse_list(resp.text, list_url)
        articles: list[RawArticle] = []
        failures: list[dict] = []
        sem = asyncio.Semaphore(5)

        async def fetch_one(ref):
            async with sem:
                key = url_hash(ref.url)
                if self.has_seen(key):
                    return
                try:
                    resp = await self._http.get(ref.url)
                    resp.raise_for_status()
                except Exception as e:
                    failures.append({"url": ref.url, "error": str(e)})
                    return
                self.set_seen(key)
                self.set_seen(content_hash(resp.text))
                articles.append(adapter.parse_detail(resp.text, ref))

        await asyncio.gather(*(fetch_one(r) for r in refs))
        return articles, failures

    async def close(self) -> None:
        await self._http.aclose()
```

- [ ] **Step 5: 运行测试通过并提交**

Run: `uv run pytest tests/test_dedup.py tests/test_engine.py -v`
Expected: PASS（4 passed）

```bash
git add collector/ tests/test_dedup.py tests/test_engine.py
git commit -m "feat: 爬虫引擎+增量去重(URL/内容哈希)"
```

### Task B3: 解析模块（trafilatura 提取 + 元数据 + LLM 兜底）

**Files:**
- Create: `collector/parser/__init__.py`、`collector/parser/extract.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- Consumes: `RawArticle`（B1）、`shared.clients.get_llm`
- Produces:
  - `ParsedArticle`（dataclass：`url/title/content/publish_date/department/source_site/column/raw_html`）
  - `collector.parser.extract.extract_article(raw: RawArticle) -> ParsedArticle`（trafilatura 主；失败或正文 <50 字时 `llm_extract` 兜底；仍 <20 字抛 `ExternalServiceError`）

- [ ] **Step 1: 写失败测试 tests/test_parser.py**

```python
from collector.crawler.base import RawArticle
from collector.parser.extract import extract_article

DETAIL_HTML = """
<html><head><title>关于2026年暑假放假安排的通知</title></head>
<body>
<div class="content">
<h1>关于2026年暑假放假安排的通知</h1>
<div class="info">发布时间：2026-06-20&nbsp;&nbsp;来源：校长办公室</div>
<p>全校各单位：根据学校校历安排，2026年暑假自7月15日起至8月31日止。</p>
<p>请各单位做好假期值班安排。</p>
</div>
</body></html>
"""


def test_extract_title_content():
    raw = RawArticle(url="https://www.gzhu.edu.cn/info/1087/1.htm", title="占位",
                     html=DETAIL_HTML, publish_date=None, source_site="gzhu", column="通知公告")
    parsed = extract_article(raw)
    assert "关于2026年暑假放假安排的通知" in parsed.title
    assert "暑假" in parsed.content and "值班" in parsed.content
    assert parsed.url == raw.url
    assert parsed.raw_html == DETAIL_HTML
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_parser.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 collector/parser/extract.py**

```python
"""正文提取：trafilatura 为主，DeepSeek 兜底结构化提取。"""
import json
import re
from dataclasses import dataclass

import trafilatura

from collector.crawler.base import RawArticle
from shared.clients import get_llm
from shared.config import settings
from shared.errors import ExternalServiceError
from shared.logging import get_logger

logger = get_logger("collector.parser")

LLM_EXTRACT_PROMPT = """你是校务文档解析器。从下面 HTML 中提取文章信息，只输出 JSON，不要输出其他内容。
JSON 格式：{{"title": "标题", "content": "正文（纯文本，保留段落）", "publish_date": "YYYY-MM-DD 或 null", "department": "发布部门或 null"}}

HTML:
{html}"""


@dataclass
class ParsedArticle:
    url: str
    title: str
    content: str
    publish_date: str | None
    department: str | None
    source_site: str
    column: str
    raw_html: str


def extract_article(raw: RawArticle) -> ParsedArticle:
    text = trafilatura.extract(raw.html, include_comments=False, include_tables=False) or ""
    title = _extract_title(raw.html) or raw.title
    publish_date = _extract_date(raw.html) or raw.publish_date
    department = _extract_department(raw.html)
    if len(text.strip()) < 50:
        logger.warning("trafilatura 提取过短(%d字)，走 LLM 兜底: %s", len(text.strip()), raw.url)
        fallback = llm_extract(raw.html)
        text = fallback.get("content", text)
        title = fallback.get("title") or title
        publish_date = fallback.get("publish_date") or publish_date
        department = fallback.get("department") or department
    if len(text.strip()) < 20:
        raise ExternalServiceError(f"正文提取失败: {raw.url}")
    return ParsedArticle(url=raw.url, title=title, content=text.strip(),
                         publish_date=publish_date, department=department,
                         source_site=raw.source_site, column=raw.column, raw_html=raw.html)


def llm_extract(html: str) -> dict:
    client = get_llm()
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[{"role": "user", "content": LLM_EXTRACT_PROMPT.format(html=html[:20000])}],
        temperature=0,
    )
    content = resp.choices[0].message.content or "{}"
    m = re.search(r"\{.*\}", content, re.S)
    return json.loads(m.group(0)) if m else {}


def _extract_title(html: str) -> str:
    for tag in ("<h1[^>]*>(.*?)</h1>", "<title[^>]*>(.*?)</title>"):
        m = re.search(tag, html, re.S | re.I)
        if m:
            return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


def _extract_date(html: str) -> str | None:
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", html)
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def _extract_department(html: str) -> str | None:
    m = re.search(r"来源[:：]\s*([^\s<&]{2,30})", html)
    return m.group(1).strip() if m else None
```

- [ ] **Step 4: 运行测试通过并提交**

Run: `uv run pytest tests/test_parser.py -v`
Expected: PASS

```bash
git add collector/parser/ tests/test_parser.py
git commit -m "feat: 解析模块(trafilatura+LLM兜底)"
```

### Task B4: 打标模块（一级分类规则 + 专题域 LLM 批量）

**Files:**
- Create: `collector/tagger/__init__.py`、`collector/tagger/rules.py`、`collector/tagger/llm_topics.py`
- Test: `tests/test_tagger.py`

**Interfaces:**
- Consumes: `ParsedArticle`（B3）、`shared.clients.get_llm`
- Produces:
  - `collector.tagger.rules.CATEGORIES = ["通知公告", "办事指南", "规章制度", "新闻动态"]`
  - `collector.tagger.rules.classify_category(title: str, column: str) -> str`
  - `collector.tagger.llm_topics.TOPICS = ["新生入学", "港澳生服务", "教务学籍", "后勤生活", "就业创业", "科研学术"]`
  - `collector.tagger.llm_topics.batch_tag_topics(articles: list[ParsedArticle], llm=None) -> dict[str, list[str]]`（key=url；LLM 失败返回 `{}` 由规则兜底；llm 参数供测试注入）

- [ ] **Step 1: 写失败测试 tests/test_tagger.py**

```python
from collector.tagger.rules import classify_category


def test_classify_notice():
    assert classify_category("关于2026年暑假放假安排的通知", "通知公告") == "通知公告"
    assert classify_category("关于给予曾玮等14名学生退学处理的预公告", "通知公告") == "通知公告"


def test_classify_guide():
    assert classify_category("本科生转专业申请办理流程", "未知栏目") == "办事指南"


def test_classify_regulation():
    assert classify_category("广州大学学生住宿管理办法", "未知栏目") == "规章制度"


def test_classify_news_fallback():
    assert classify_category("我校荣获2026年教学成果一等奖", "新闻动态") == "新闻动态"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_tagger.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 collector/tagger/rules.py**

```python
"""一级分类：规则打标（来源栏目映射 + 标题关键词）。"""

CATEGORIES = ["通知公告", "办事指南", "规章制度", "新闻动态"]

RULE_KEYWORDS = {
    "通知公告": ["通知", "公告", "公示", "通告", "安排"],
    "办事指南": ["指南", "流程", "办事", "办理", "申请", "须知"],
    "规章制度": ["规定", "办法", "制度", "条例", "细则", "章程"],
}

COLUMN_TO_CATEGORY = {
    "通知公告": "通知公告",
    "新闻动态": "新闻动态",
}


def classify_category(title: str, column: str) -> str:
    """栏目映射优先；其次标题关键词；兜底新闻动态。"""
    if column in COLUMN_TO_CATEGORY:
        return COLUMN_TO_CATEGORY[column]
    for category, words in RULE_KEYWORDS.items():
        if any(w in title for w in words):
            return category
    return "新闻动态"
```

- [ ] **Step 4: 实现 collector/tagger/llm_topics.py**

```python
"""二级专题域：LLM 批量打标（可离线批处理，失败返回空由规则兜底）。"""
import json
import re

from collector.parser.extract import ParsedArticle
from shared.clients import get_llm
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("collector.tagger")

TOPICS = ["新生入学", "港澳生服务", "教务学籍", "后勤生活", "就业创业", "科研学术"]

TOPIC_PROMPT = """你是校务知识打标助手。给每篇文章从下列专题域中选择最相关的（可多选、可空）：
专题域：{topics}
文章列表（编号|标题|摘要）：
{items}

只输出 JSON：{{"<编号>": ["专题域1", ...]}}"""


async def batch_tag_topics(articles: list[ParsedArticle], llm=None) -> dict[str, list[str]]:
    """返回 {url: [topics]}；失败返回空 dict（规则兜底）。"""
    if not articles:
        return {}
    items = "\n".join(f"{i}|{a.title}|{a.content[:80]}" for i, a in enumerate(articles))
    prompt = TOPIC_PROMPT.format(topics=",".join(TOPICS), items=items)
    try:
        client = llm or get_llm()
        resp = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = resp.choices[0].message.content or "{}"
        m = re.search(r"\{.*\}", content, re.S)
        data = json.loads(m.group(0)) if m else {}
        result: dict[str, list[str]] = {}
        for key, topics in data.items():
            if key.isdigit() and int(key) < len(articles):
                valid = [t for t in topics if t in TOPICS]
                if valid:
                    result[articles[int(key)].url] = valid
        return result
    except Exception as e:
        logger.warning("专题域 LLM 打标失败，规则兜底: %s", e)
        return {}
```

- [ ] **Step 5: 运行测试通过并提交**

Run: `uv run pytest tests/test_tagger.py -v`
Expected: PASS（4 passed）

```bash
git add collector/tagger/ tests/test_tagger.py
git commit -m "feat: 打标模块(一级规则+专题域LLM批量)"
```

### Task B5: 时效模块（有效期推断 + 过期判定）

**Files:**
- Create: `collector/lifecycle/__init__.py`、`collector/lifecycle/validity.py`
- Test: `tests/test_validity.py`

**Interfaces:**
- Consumes: `ParsedArticle`（B3）、`collector.tagger.rules.classify_category`（B4）
- Produces:
  - `collector.lifecycle.validity.infer_expiry(title: str, content: str, category: str, publish_date: str) -> str | None`（返回 `YYYY-MM-DD`；"截止/截至/有效期至/报名截止"正则优先；通知公告默认 90 天；办事指南/规章制度无默认有效期返回 None）
  - `collector.lifecycle.validity.is_expired(expire_at: str | None, now: datetime) -> bool`

- [ ] **Step 1: 写失败测试 tests/test_validity.py**

```python
from datetime import datetime

from collector.lifecycle.validity import infer_expiry, is_expired


def test_infer_from_deadline_text():
    assert infer_expiry("关于2026年挑战杯报名通知", "报名截止时间为2026年9月15日", "通知公告", "2026-08-01") == "2026-09-15"


def test_infer_from_validity_text():
    assert infer_expiry("图书馆服务调整公告", "本公告有效期至2026年12月31日", "通知公告", "2026-08-01") == "2026-12-31"


def test_default_for_notice():
    assert infer_expiry("关于暑假放假安排的通知", "全校各单位：暑假自7月15日起。", "通知公告", "2026-06-20") == "2026-09-18"


def test_none_for_guide():
    assert infer_expiry("本科生转专业申请办理流程", "第一步：提交申请材料。", "办事指南", "2026-01-01") is None


def test_is_expired():
    assert is_expired("2026-08-01", datetime(2026, 9, 1))
    assert not is_expired("2026-08-01", datetime(2026, 7, 1))
    assert not is_expired(None, datetime(2026, 9, 1))
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_validity.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 collector/lifecycle/validity.py**

```python
"""时效推断：截止日期识别 + 类别默认有效期 + 过期判定。"""
import re
from datetime import datetime, timedelta

NOTICE_DEFAULT_DAYS = 90

DEADLINE_PATTERNS = [
    r"(?:报名)?截止(?:时间|日期)?[:：]?\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
    r"截至\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
    r"有效期至\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
]


def infer_expiry(title: str, content: str, category: str, publish_date: str) -> str | None:
    """推断有效期截止日；无法推断且类别无默认值时返回 None。"""
    text = title + " " + content
    for pattern in DEADLINE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if category == "通知公告":
        pub = datetime.strptime(publish_date, "%Y-%m-%d")
        return (pub + timedelta(days=NOTICE_DEFAULT_DAYS)).strftime("%Y-%m-%d")
    return None


def is_expired(expire_at: str | None, now: datetime) -> bool:
    if expire_at is None:
        return False
    return datetime.strptime(expire_at, "%Y-%m-%d") < now
```

- [ ] **Step 4: 运行测试通过并提交**

Run: `uv run pytest tests/test_validity.py -v`
Expected: PASS（5 passed）

```bash
git add collector/lifecycle/ tests/test_validity.py
git commit -m "feat: 时效模块(截止日期识别+默认有效期)"
```

### Task B6: 切分 + 向量化 + 三写入库（幂等）

**Files:**
- Create: `collector/ingest/__init__.py`、`collector/ingest/splitter.py`、`collector/ingest/writer.py`
- Test: `tests/test_splitter.py`、`tests/test_ingest_idempotent.py`

**Interfaces:**
- Consumes: `ParsedArticle`（B3）、`classify_category`（B4）、`infer_expiry`（B5）、`shared.clients`、`shared.config.settings`
- Produces:
  - `collector.ingest.splitter.split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]`
  - `collector.ingest.writer.ingest_document(parsed: ParsedArticle, category: str, topics: list[str], expire_at: str | None, embed_fn=None, milvus=None, mongo_db=None, minio=None) -> str`（返回 doc_id；**先删后插幂等**；MinIO 失败降级跳过快照；embed_fn 供测试注入）
  - `collector.ingest.writer.ensure_collection(milvus)`（Milvus 集合与索引创建：dense COSINE、sparse IP）

- [ ] **Step 1: 写失败测试 tests/test_splitter.py**

```python
from collector.ingest.splitter import split_text


def test_split_short_text_single_chunk():
    assert split_text("短短一篇。", chunk_size=500) == ["短短一篇。"]


def test_split_long_text_with_overlap():
    text = "段落一。" * 300  # 1200 字
    chunks = split_text(text, chunk_size=500, overlap=50)
    assert len(chunks) >= 3
    assert all(len(c) <= 500 for c in chunks)
    # 拼接检查：所有 chunk 内容都来自原文
    joined = "".join(chunks)
    assert "段落一" in joined
```

- [ ] **Step 2: 写失败测试 tests/test_ingest_idempotent.py**

```python
import pytest

from collector.parser.extract import ParsedArticle
from collector.ingest.writer import ingest_document


class FakeMilvus:
    def __init__(self):
        self.rows = []
        self.deleted = []

    def delete(self, collection_name, filter, **kwargs):
        self.deleted.append(filter)
        return {"delete_count": len(self.rows)}

    def insert(self, collection_name, data, **kwargs):
        self.rows.extend(data)
        return {"insert_count": len(data)}


class FakeMongo:
    def __init__(self):
        self.docs = []

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
    assert doc_id.startswith("doc-")
    assert len(mongo.docs) == 1
    assert mongo.docs[0]["snapshot_missing"] is True
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/test_splitter.py tests/test_ingest_idempotent.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 4: 实现 collector/ingest/splitter.py**

```python
"""文本切分：按字符滑窗切块（中文友好）。"""


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks
```

- [ ] **Step 5: 实现 collector/ingest/writer.py**

```python
"""三写入库：切分→向量化→Milvus 向量 + MongoDB 元数据 + MinIO 快照（幂等：先删后插）。"""
import hashlib
from datetime import datetime

from collector.ingest.splitter import split_text
from collector.parser.extract import ParsedArticle
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("collector.ingest")


def doc_id_of(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def ensure_collection(milvus) -> None:
    """创建集合与索引：dense COSINE、sparse IP。"""
    if milvus.has_collection(settings.milvus_collection):
        return
    milvus.create_collection(
        collection_name=settings.milvus_collection,
        dimension=1024,
        metric_type="COSINE",
        primary_field_name="id",
        vector_field_name="dense_vector",
    )
    milvus.add_index(settings.milvus_collection, "dense_vector",
                     {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}})
    milvus.add_index(settings.milvus_collection, "sparse_vector",
                     {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "IP"})


async def ingest_document(parsed: ParsedArticle, category: str, topics: list[str], expire_at: str | None,
                          embed_fn=None, milvus=None, mongo_db=None, minio=None) -> str:
    """幂等入库：先按 doc_id 删除旧数据再插入新数据。返回 doc_id。（motor 异步，所有 Mongo 调用必须 await）"""
    from shared.clients import get_milvus, get_minio, get_mongo

    milvus = milvus or get_milvus()
    mongo_db = mongo_db or get_mongo()
    minio = minio or get_minio()
    embed_fn = embed_fn or _embed_batch

    doc_id = doc_id_of(parsed.url)
    chunks = split_text(parsed.content)
    embeddings = embed_fn(chunks)

    # 幂等：先删后插
    milvus.delete(settings.milvus_collection, filter=f'doc_id == "{doc_id}"')
    collection = mongo_db["documents"]
    existing = await collection.find_one({"doc_id": doc_id})
    if existing:
        await collection.delete_many({"doc_id": doc_id})

    # MinIO 快照（降级：失败标记缺失）
    snapshot_missing = False
    try:
        minio.put_object(settings.minio_bucket, f"snapshots/{doc_id}.html",
                         parsed.raw_html.encode(), len(parsed.raw_html.encode()),
                         content_type="text/html")
    except Exception as e:
        logger.warning("MinIO 快照失败(降级): %s", e)
        snapshot_missing = True

    # MongoDB 元数据
    meta = {
        "doc_id": doc_id,
        "url": parsed.url,
        "title": parsed.title,
        "publish_date": parsed.publish_date,
        "department": parsed.department,
        "source_site": parsed.source_site,
        "column": parsed.column,
        "category": category,
        "topics": topics,
        "expire_at": expire_at,
        "status": "active",
        "snapshot_missing": snapshot_missing,
        "chunk_count": len(chunks),
        "ingested_at": datetime.now().isoformat(),
    }
    await collection.insert_one(meta)

    # Milvus 向量（每个 chunk 一行）
    rows = []
    now_ts = int(datetime.now().timestamp())
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        rows.append({
            "id": f"{doc_id}_{i}",
            "doc_id": doc_id,
            "chunk_idx": i,
            "text": chunk,
            "dense_vector": emb["dense"],
            "sparse_vector": emb["sparse"],
            "category": category,
            "topics": topics,
            "publish_date": parsed.publish_date or "",
            "expire_at": expire_at or "",
            "status": "active",
            "ingested_ts": now_ts,
        })
    if rows:
        milvus.insert(settings.milvus_collection, rows)
    logger.info("入库完成 doc=%s chunks=%d", doc_id, len(chunks))
    return doc_id


def _embed_batch(texts: list[str]) -> list[dict]:
    import httpx

    resp = httpx.post(f"{settings.embed_service_url}/embed", json={"texts": texts},
                      timeout=settings.external_timeout)
    resp.raise_for_status()
    return resp.json()["embeddings"]
```

- [ ] **Step 6: 运行测试通过并提交**

Run: `uv run pytest tests/test_splitter.py tests/test_ingest_idempotent.py -v`
Expected: PASS（4 passed）

```bash
git add collector/ingest/ tests/test_splitter.py tests/test_ingest_idempotent.py
git commit -m "feat: 切分+三写入库(幂等先删后插,MinIO降级)"
```

### Task B7: 采集任务状态机 + APScheduler 调度

**Files:**
- Create: `collector/tasks.py`
- Create: `collector/scheduler.py`
- Create: `collector/sources.py`（采集源配置 CRUD，MongoDB 存储）
- Test: `tests/test_tasks.py`

**Interfaces:**
- Consumes: `CrawlEngine`（B2）、`extract_article`（B3）、`classify_category/batch_tag_topics`（B4）、`infer_expiry`（B5）、`ingest_document`（B6）、`shared.clients`
- Produces:
  - `collector.sources.SourceConfig`（dataclass：`id/name/list_url/adapter/enabled/interval_minutes`）
  - `collector.sources.list_sources() -> list[SourceConfig]`、`save_source(cfg)`、`delete_source(id)`（MongoDB `sources` 集合）
  - `collector.tasks.TaskStatus = "pending" | "running" | "success" | "partial" | "failed"`
  - `collector.tasks.run_collection_task(source_id: str) -> dict`（任务状态机；成功 N/失败 M；失败重试 3 次；结果写 MongoDB `task_runs`）
  - `collector.scheduler.start_scheduler(app)`（AsyncIOScheduler 装配：扫描 enabled 采集源注册周期任务）

- [ ] **Step 1: 写失败测试 tests/test_tasks.py**

```python
from unittest.mock import AsyncMock

from collector import tasks as tasks_mod


async def test_run_task_partial_failure(monkeypatch):
    """单页失败→部分失败状态；结果记录成功/失败数。"""
    fake_engine = AsyncMock()
    fake_engine.fetch_source = AsyncMock(return_value=([], [{"url": "https://x/1.htm", "error": "超时"}]))
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: fake_engine)
    fake_mongo = AsyncMock()
    fake_mongo.find_one = AsyncMock(return_value=None)
    fake_mongo.insert_one = AsyncMock()
    fake_mongo.update_one = AsyncMock()
    monkeypatch.setattr(tasks_mod, "get_mongo", lambda: fake_mongo)
    source = tasks_mod.SourceConfig(id="s1", name="主站公告", list_url="https://www.gzhu.edu.cn/z__l/tzgg.htm",
                                    adapter="gzhu", enabled=True, interval_minutes=60)
    result = await tasks_mod.run_collection_task(source)
    assert result["status"] == "partial"
    assert result["failed"] == 1
    assert result["succeeded"] == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_tasks.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 collector/sources.py**

```python
"""采集源配置 CRUD（MongoDB sources 集合）。"""
import uuid
from dataclasses import asdict, dataclass

from shared.clients import get_mongo
from shared.logging import get_logger

logger = get_logger("collector.sources")

ADAPTERS = {"gzhu": "collector.crawler.gzhu.GUZhuAdapter", "gznews": "collector.crawler.gznews.GUNewsAdapter"}


@dataclass
class SourceConfig:
    id: str
    name: str
    list_url: str
    adapter: str
    enabled: bool = True
    interval_minutes: int = 360

    @staticmethod
    def from_dict(d: dict) -> "SourceConfig":
        return SourceConfig(id=d["id"], name=d["name"], list_url=d["list_url"],
                            adapter=d["adapter"], enabled=d.get("enabled", True),
                            interval_minutes=d.get("interval_minutes", 360))


def list_sources() -> list[SourceConfig]:
    db = get_mongo()
    docs = db["sources"].find({"enabled": True})
    return [SourceConfig.from_dict(d) for d in docs]


def list_all_sources() -> list[SourceConfig]:
    db = get_mongo()
    docs = db["sources"].find()
    return [SourceConfig.from_dict(d) for d in docs]


def save_source(cfg: SourceConfig) -> str:
    if not cfg.id:
        cfg.id = uuid.uuid4().hex[:12]
    get_mongo()["sources"].update_one({"id": cfg.id}, {"$set": asdict(cfg)}, upsert=True)
    return cfg.id


def delete_source(source_id: str) -> bool:
    result = get_mongo()["sources"].delete_one({"id": source_id})
    return result.deleted_count > 0
```

- [ ] **Step 4: 实现 collector/tasks.py**

```python
"""采集任务状态机：pending→running→success/partial/failed；逐页隔离；重试 3 次。"""
import asyncio
from datetime import datetime

from collector.crawler.engine import CrawlEngine
from collector.lifecycle.validity import infer_expiry
from collector.parser.extract import extract_article
from collector.sources import SourceConfig
from collector.tagger.llm_topics import batch_tag_topics
from collector.tagger.rules import classify_category
from shared.clients import get_mongo
from shared.errors import ExternalServiceError
from shared.logging import get_logger
from shared.retry import async_retry

logger = get_logger("collector.tasks")

ADAPTER_IMPORT = {
    "gzhu": "collector.crawler.gzhu",
    "gznews": "collector.crawler.gznews",
}


def _load_adapter(name: str):
    module = __import__(ADAPTER_IMPORT[name], fromlist=["*"])
    return module.GUZhuAdapter() if name == "gzhu" else module.GUNewsAdapter()


@async_retry(retries=3, base_delay=2.0, max_delay=30.0)
async def _fetch_with_retry(engine: CrawlEngine, source: SourceConfig):
    return await engine.fetch_source(source.list_url, _load_adapter(source.adapter))


async def run_collection_task(source: SourceConfig) -> dict:
    """执行一次采集任务，状态写入 MongoDB task_runs。"""
    from collector.ingest.writer import ingest_document

    db = get_mongo()
    task_id = f"{source.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    run_doc = {"task_id": task_id, "source_id": source.id, "status": "running",
               "started_at": datetime.now().isoformat(), "succeeded": 0, "failed": 0, "failures": []}
    await db["task_runs"].insert_one(run_doc)
    logger.info("任务开始 %s", task_id)

    engine = CrawlEngine()
    try:
        raw_articles, failures = await _fetch_with_retry(engine, source)
    except ExternalServiceError as e:
        await db["task_runs"].update_one({"task_id": task_id},
                                         {"$set": {"status": "failed", "finished_at": datetime.now().isoformat(),
                                                   "error": str(e)}})
        return {"task_id": task_id, "status": "failed", "succeeded": 0, "failed": 0}
    finally:
        await engine.close()

    parsed = []
    for raw in raw_articles:
        try:
            parsed.append(extract_article(raw))
        except ExternalServiceError as e:
            failures.append({"url": raw.url, "error": str(e), "stage": "parse"})

    topics_map = await batch_tag_topics(parsed)
    succeeded = 0
    for art in parsed:
        try:
            category = classify_category(art.title, art.column)
            expire_at = infer_expiry(art.title, art.content, category, art.publish_date or "")
            await ingest_document(art, category, topics_map.get(art.url, []), expire_at)
            succeeded += 1
        except Exception as e:
            failures.append({"url": art.url, "error": str(e), "stage": "ingest"})

    status = "success" if not failures else ("partial" if succeeded else "failed")
    await db["task_runs"].update_one({"task_id": task_id},
                                     {"$set": {"status": status, "succeeded": succeeded,
                                               "failed": len(failures), "failures": failures,
                                               "finished_at": datetime.now().isoformat()}})
    logger.info("任务结束 %s status=%s 成功=%d 失败=%d", task_id, status, succeeded, len(failures))
    return {"task_id": task_id, "status": status, "succeeded": succeeded, "failed": len(failures)}
```

- [ ] **Step 5: 实现 collector/scheduler.py**

```python
"""APScheduler 装配：enabled 采集源注册周期任务。"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from collector.sources import list_sources
from collector.tasks import run_collection_task
from shared.logging import get_logger

logger = get_logger("collector.scheduler")
_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    for source in list_sources():
        _scheduler.add_job(
            run_collection_task, IntervalTrigger(minutes=source.interval_minutes),
            args=[source], id=f"collect-{source.id}", replace_existing=True,
        )
    _scheduler.start()
    logger.info("调度器已启动，共 %d 个采集源", len(list_sources()))


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
```

- [ ] **Step 6: 运行测试通过并提交**

Run: `uv run pytest tests/test_tasks.py -v`
Expected: PASS

```bash
git add collector/tasks.py collector/scheduler.py collector/sources.py tests/test_tasks.py
git commit -m "feat: 采集任务状态机+APScheduler调度"
```

### Task B8: 采集服务管理端 API + 生命周期 + 统计

**Files:**
- Create: `collector/knowledge.py`
- Create: `collector/api/__init__.py`、`collector/api/sources.py`、`collector/api/tasks.py`、`collector/api/knowledge.py`
- Create: `collector/main.py`
- Create: `collector/Dockerfile`

**Interfaces:**
- Consumes: B1~B7 全部；`shared.clients`
- Produces（HTTP，前端 Plan 2 依赖）:
  - `GET/POST /api/admin/sources`、`DELETE /api/admin/sources/{id}`（body：`{"name","list_url","adapter","interval_minutes","enabled"}`）
  - `POST /api/admin/sources/{id}/run` → 任务触发（后台执行），返回 `{"task_id"}`
  - `GET /api/admin/tasks?source_id=&limit=` → `{"items":[{"task_id","status","succeeded","failed","started_at","finished_at"}]}`
  - `GET /api/admin/knowledge?status=&category=&topic=&page=&page_size=` → `{"items":[文档元数据],"total"}`
  - `POST /api/admin/knowledge/{doc_id}/status` body `{"status": "active|archived"}` → 人工上下架（Mongo 状态 + Milvus 状态同步）
  - `GET /api/admin/stats` → 资产全景（总量/分类分布/时效分布/专题域分布/近期任务）
  - `POST /api/admin/expiry-check` → 到期检测（将过期文档置 expired 并降权）
  - `collector.knowledge.asset_stats() -> dict`、`collector.knowledge.check_expiry() -> int`（置为 expired 的文档数）

- [ ] **Step 1: 实现 collector/knowledge.py（知识库查询/上下架/统计/到期检测）**

```python
"""知识库管理：查询/上下架/统计/到期检测。（motor 异步：所有 Mongo 调用必须 await）"""
from datetime import datetime

from shared.clients import get_mongo
from shared.logging import get_logger

logger = get_logger("collector.knowledge")


async def query_documents(status: str | None = None, category: str | None = None, topic: str | None = None,
                          page: int = 1, page_size: int = 20) -> dict:
    query = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if topic:
        query["topics"] = topic
    collection = get_mongo()["documents"]
    total = await collection.count_documents(query)
    cursor = collection.find(query).sort("ingested_at", -1).skip((page - 1) * page_size).limit(page_size)
    items = []
    async for d in cursor:
        d.pop("_id", None)
        items.append(d)
    return {"items": items, "total": total}


async def set_doc_status(doc_id: str, status: str) -> bool:
    """人工上下架：更新 Mongo 状态；Milvus 状态在检索侧按 Mongo 状态过滤（简化版）。"""
    assert status in ("active", "archived")
    result = await get_mongo()["documents"].update_one({"doc_id": doc_id}, {"$set": {"status": status}})
    return result.matched_count > 0


async def check_expiry() -> int:
    """到期检测：expire_at 已过且仍为 active 的文档置为 expired。返回数量。"""
    collection = get_mongo()["documents"]
    now_str = datetime.now().strftime("%Y-%m-%d")
    result = await collection.update_many(
        {"expire_at": {"$ne": None, "$lt": now_str}, "status": "active"},
        {"$set": {"status": "expired"}},
    )
    return result.modified_count


async def asset_stats() -> dict:
    db = get_mongo()
    docs = db["documents"]
    total = await docs.count_documents({})
    by_category = {}
    async for d in docs.aggregate([{"$group": {"_id": "$category", "count": {"$sum": 1}}}]):
        by_category[d["_id"]] = d["count"]
    by_status = {}
    async for d in docs.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
        by_status[d["_id"]] = d["count"]
    by_topic = {}
    async for d in docs.aggregate([{"$unwind": {"path": "$topics", "preserveNullAndEmptyArrays": True}},
                                   {"$group": {"_id": "$topics", "count": {"$sum": 1}}}]):
        by_topic[str(d["_id"])] = d["count"]
    recent_tasks = []
    cursor = db["task_runs"].find().sort("started_at", -1).limit(5)
    async for t in cursor:
        t.pop("_id", None)
        recent_tasks.append(t)
    # 问答热度（反哺"该采集什么"）
    qa_logs = db["qa_logs"]
    qa_total = await qa_logs.count_documents({})
    hot_queries = []
    async for d in qa_logs.aggregate([{"$group": {"_id": "$query", "count": {"$sum": 1}}},
                                      {"$sort": {"count": -1}}, {"$limit": 5}]):
        hot_queries.append({"query": d["_id"], "count": d["count"]})
    return {"total_docs": total, "by_category": by_category, "by_status": by_status,
            "by_topic": by_topic, "recent_tasks": recent_tasks,
            "qa_total": qa_total, "hot_queries": hot_queries}
```

- [ ] **Step 2: 实现 collector/api/sources.py、tasks.py、knowledge.py**

```python
# collector/api/sources.py
"""采集源管理 API。"""
from fastapi import APIRouter

from collector import sources
from collector.sources import SourceConfig

router = APIRouter(prefix="/api/admin/sources", tags=["采集源"])


@router.get("")
def get_sources():
    return {"items": [s.__dict__ for s in sources.list_all_sources()]}


@router.post("")
def create_source(payload: dict):
    cfg = SourceConfig(id="", name=payload["name"], list_url=payload["list_url"],
                       adapter=payload["adapter"], enabled=payload.get("enabled", True),
                       interval_minutes=payload.get("interval_minutes", 360))
    return {"id": sources.save_source(cfg)}


@router.delete("/{source_id}")
def remove_source(source_id: str):
    return {"deleted": sources.delete_source(source_id)}
```

```python
# collector/api/tasks.py
"""采集任务触发与查询 API。"""
import asyncio

from fastapi import APIRouter

from collector import sources
from collector.tasks import run_collection_task
from shared.clients import get_mongo

router = APIRouter(prefix="/api/admin/tasks", tags=["采集任务"])


@router.post("/{source_id}/run")
async def trigger_run(source_id: str):
    target = next((s for s in sources.list_all_sources() if s.id == source_id), None)
    if target is None:
        return {"error": "采集源不存在"}
    asyncio.create_task(run_collection_task(target))
    return {"started": True, "source_id": source_id}


@router.get("")
async def list_tasks(source_id: str | None = None, limit: int = 20):
    query = {"source_id": source_id} if source_id else {}
    items = []
    cursor = get_mongo()["task_runs"].find(query).sort("started_at", -1).limit(limit)
    async for t in cursor:
        t.pop("_id", None)
        items.append(t)
    return {"items": items}
```

```python
# collector/api/knowledge.py
"""知识库管理 API。"""
from fastapi import APIRouter

from collector import knowledge

router = APIRouter(prefix="/api/admin", tags=["知识库"])


@router.get("/knowledge")
async def list_knowledge(status: str | None = None, category: str | None = None, topic: str | None = None,
                         page: int = 1, page_size: int = 20):
    return await knowledge.query_documents(status, category, topic, page, page_size)


@router.post("/knowledge/{doc_id}/status")
async def change_status(doc_id: str, payload: dict):
    return {"updated": await knowledge.set_doc_status(doc_id, payload["status"])}


@router.get("/stats")
async def stats():
    return await knowledge.asset_stats()


@router.post("/expiry-check")
async def expiry_check():
    return {"expired_count": await knowledge.check_expiry()}
```

- [ ] **Step 3: 实现 collector/main.py 与 Dockerfile**

```python
"""采集服务入口：FastAPI + 调度器生命周期。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from collector.api import knowledge as knowledge_api
from collector.api import sources as sources_api
from collector.api import tasks as tasks_api
from collector.scheduler import start_scheduler, stop_scheduler
from shared.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="校务中台·采集服务", lifespan=lifespan)
app.include_router(sources_api.router)
app.include_router(tasks_api.router)
app.include_router(knowledge_api.router)
```

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY shared ./shared
COPY collector ./collector
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx selectolax trafilatura apscheduler motor pymilvus minio openai pydantic python-dotenv
ENV EMBED_SERVICE_URL=http://model-server:8001
EXPOSE 8002
CMD ["uvicorn", "collector.main:app", "--host", "0.0.0.0", "--port", "8002"]
```

- [ ] **Step 4: 冒烟验证（本地直跑，依赖 WSL 现有存储）**

Run: `uv run uvicorn collector.main:app --port 8002`，然后：
`curl -s http://localhost:8002/api/admin/stats`
Expected: 返回 `{"total_docs": 0, ...}`（需 Milvus/Mongo 可达）

- [ ] **Step 5: 提交**

```bash
git add collector/
git commit -m "feat: 采集服务API(采集源/任务/知识库/统计/到期检测)+main"
```

---

## 阶段 C：问答链路（派发 glm-5.3 批量，Task C1~C4 一批）

### Task C1: 检索模块（混合检索 + 元数据过滤 + 时间衰减 + 过期降权）

**Files:**
- Create: `qa_api/__init__.py`、`qa_api/retriever/__init__.py`、`qa_api/retriever/hybrid.py`
- Test: `tests/test_hybrid.py`

**Interfaces:**
- Consumes: `shared.config.settings`、`shared.clients.get_milvus`
- Produces:
  - `ScoredChunk`（dataclass：`chunk_id/doc_id/text/score/dense_score/sparse_score/category/topics/publish_date/expire_at/status/expired: bool`）
  - `qa_api.retriever.hybrid.hybrid_search(query: str, category: str | None = None, topics: list[str] | None = None, top_k: int = 10, milvus=None, embed_fn=None) -> list[ScoredChunk]`（dense/sparse 两路检索→norm_score min-max 归一化→加权融合（dense 0.8+sparse 0.2）→时间衰减 `0.5**(days/30)`→过期再乘 0.25 并置 expired 标记→过滤排序取 top_k）

- [ ] **Step 1: 写失败测试 tests/test_hybrid.py**

```python
from datetime import datetime, timedelta

from qa_api.retriever.hybrid import ScoredChunk, apply_time_decay


def test_time_decay_half_life_30d():
    now = datetime(2026, 9, 1)
    pub = datetime(2026, 8, 2)  # 30 天前
    factor = apply_time_decay(pub.strftime("%Y-%m-%d"), now, half_life_days=30)
    assert abs(factor - 0.5) < 1e-6
    fresh = now - timedelta(days=1)
    assert apply_time_decay(fresh.strftime("%Y-%m-%d"), now, half_life_days=30) > 0.9


def test_time_decay_ignores_missing_date():
    assert apply_time_decay("", datetime(2026, 9, 1), half_life_days=30) == 1.0


def test_expired_penalty_applied():
    chunk = ScoredChunk(chunk_id="d_0", doc_id="d", text="t", score=0.9,
                        dense_score=0.9, sparse_score=0.9, category="通知公告",
                        topics=[], publish_date="2026-08-01", expire_at="2026-08-10",
                        status="expired", expired=False)
    penalized = apply_expired_penalty(chunk, 0.25)
    assert penalized.expired is True
    assert abs(penalized.score - 0.9 * 0.25) < 1e-9


def test_norm_score_fusion():
    dense_scores = [0.7, 0.3]
    sparse_scores = [0.5, 0.9]
    fused = fuse_scores(dense_scores, sparse_scores, dense_weight=0.8, sparse_weight=0.2)
    # min-max 归一化后：dense=[1.0,0.0] sparse=[0.0,1.0]
    # 融合：[0.8, 0.2]
    assert abs(fused[0] - 0.8) < 1e-9
    assert abs(fused[1] - 0.2) < 1e-9
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_hybrid.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 qa_api/retriever/hybrid.py**

```python
"""混合检索：dense+sparse 双路召回 → norm_score 融合 → 时间衰减 → 过期降权。"""
import httpx
from dataclasses import dataclass, field
from datetime import datetime

from shared.config import settings
from shared.logging import get_logger

logger = get_logger("qa_api.retriever")


@dataclass
class ScoredChunk:
    chunk_id: str
    doc_id: str
    text: str
    score: float
    dense_score: float
    sparse_score: float
    category: str = ""
    topics: list = field(default_factory=list)
    publish_date: str = ""
    expire_at: str = ""
    status: str = "active"
    expired: bool = False


def minmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def fuse_scores(dense_scores: list[float], sparse_scores: list[float],
                dense_weight: float, sparse_weight: float) -> list[float]:
    nd = minmax(dense_scores)
    ns = minmax(sparse_scores)
    return [dense_weight * d + sparse_weight * s for d, s in zip(nd, ns)]


def apply_time_decay(publish_date: str, now: datetime, half_life_days: float) -> float:
    if not publish_date:
        return 1.0
    try:
        pub = datetime.strptime(publish_date, "%Y-%m-%d")
    except ValueError:
        return 1.0
    days = max((now - pub).days, 0)
    return 0.5 ** (days / half_life_days)


def apply_expired_penalty(chunk: ScoredChunk, penalty: float) -> ScoredChunk:
    expired = chunk.status == "expired" or (chunk.expire_at and chunk.expire_at < datetime.now().strftime("%Y-%m-%d"))
    if expired:
        chunk.expired = True
        chunk.score *= penalty
    return chunk


def _embed_query(query: str) -> dict:
    resp = httpx.post(f"{settings.embed_service_url}/embed", json={"texts": [query]},
                      timeout=settings.external_timeout)
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


def _search_one(milvus, emb: dict, vector_field: str, metric: str, top_k: int, expr: str | None):
    query_vec = emb["dense"] if vector_field == "dense_vector" else emb["sparse"]
    results = milvus.search(
        collection_name=settings.milvus_collection,
        data=[query_vec],
        anns_field=vector_field,
        limit=top_k,
        filter=expr or "",
        output_fields=["doc_id", "chunk_idx", "text", "category", "topics",
                       "publish_date", "expire_at", "status"],
        search_params={"metric_type": metric, "params": {"nprobe": 16}},
    )
    return results[0] if results else []


async def hybrid_search(query: str, category: str | None = None, topics: list[str] | None = None,
                        top_k: int | None = None, milvus=None, embed_fn=None) -> list[ScoredChunk]:
    from shared.clients import get_milvus

    milvus = milvus or get_milvus()
    top_k = top_k or settings.recall_top_k
    try:
        emb = (embed_fn or _embed_query)(query)
    except Exception as e:
        logger.warning("embedding 服务不可用: %s", e)
        return []

    expr_parts = []
    if category:
        expr_parts.append(f'category == "{category}"')
    if topics:
        topic_expr = " || ".join(f'topics like "%{t}%"' for t in topics)
        expr_parts.append(f"({topic_expr})")
    expr = " && ".join(expr_parts) or None

    # dense 必跑；sparse 失败降级为全 0（主链路可用）；过滤表达式失败降级为无过滤重试
    try:
        dense_hits = _search_one(milvus, emb, "dense_vector", "COSINE", top_k, expr)
    except Exception as e:
        if expr is not None:
            logger.warning("过滤表达式执行失败，降级无过滤检索: %s", e)
            expr = None
            try:
                dense_hits = _search_one(milvus, emb, "dense_vector", "COSINE", top_k, expr)
            except Exception as e2:
                logger.warning("dense 检索异常: %s", e2)
                return []
        else:
            logger.warning("dense 检索异常: %s", e)
            return []
    try:
        sparse_hits = _search_one(milvus, emb, "sparse_vector", "IP", top_k, expr)
    except Exception as e:
        logger.warning("sparse 检索异常，降级仅 dense: %s", e)
        sparse_hits = []

    # 以 chunk_id 对齐两路结果
    dense_map = {h["id"]: h for h in dense_hits}
    sparse_map = {h["id"]: h for h in sparse_hits}
    keys = list(dict.fromkeys([h["id"] for h in dense_hits] + [h["id"] for h in sparse_hits]))
    dense_scores = [dense_map[k]["distance"] if k in dense_map else 0.0 for k in keys]
    sparse_scores = [sparse_map[k]["distance"] if k in sparse_map else 0.0 for k in keys]
    fused = fuse_scores(dense_scores, sparse_scores, settings.dense_weight, settings.sparse_weight)

    now = datetime.now()
    chunks: list[ScoredChunk] = []
    for k, score in zip(keys, fused):
        h = dense_map.get(k) or sparse_map[k]
        entity = h.get("entity", h)
        chunk = ScoredChunk(
            chunk_id=k, doc_id=entity.get("doc_id", ""), text=entity.get("text", ""),
            score=score, dense_score=dense_map[k]["distance"] if k in dense_map else 0.0,
            sparse_score=sparse_map[k]["distance"] if k in sparse_map else 0.0,
            category=entity.get("category", ""), topics=entity.get("topics", []),
            publish_date=entity.get("publish_date", ""), expire_at=entity.get("expire_at", ""),
            status=entity.get("status", "active"),
        )
        chunk.score *= apply_time_decay(chunk.publish_date, now, settings.time_decay_half_life_days)
        chunk = apply_expired_penalty(chunk, settings.expired_penalty)
        chunks.append(chunk)

    chunks.sort(key=lambda c: -c.score)
    return chunks[:top_k]
```

- [ ] **Step 4: 运行测试通过并提交**

Run: `uv run pytest tests/test_hybrid.py -v`
Expected: PASS（4 passed）

```bash
git add qa_api/ tests/test_hybrid.py
git commit -m "feat: 混合检索(双路融合+时间衰减+过期降权)"
```

### Task C2: 重排模块（reranker 精排 + 断崖截断）

**Files:**
- Create: `qa_api/reranker/__init__.py`、`qa_api/reranker/rerank.py`
- Test: `tests/test_rerank.py`

**Interfaces:**
- Consumes: `ScoredChunk`（C1）、`shared.config.settings`
- Produces:
  - `qa_api.retriever.hybrid.cliff_cutoff(chunks: list[ScoredChunk], ratio: float | None = None) -> list[ScoredChunk]`（相邻分数骤降截断，至少保留 1 条）
  - `qa_api.reranker.rerank.rerank_chunks(query: str, chunks: list[ScoredChunk], client=None) -> list[ScoredChunk]`（调 /rerank 服务按新分排序；**失败原序返回降级**）

- [ ] **Step 1: 写失败测试 tests/test_rerank.py**

```python
from qa_api.retriever.hybrid import ScoredChunk, cliff_cutoff


def make_chunk(cid, score):
    return ScoredChunk(chunk_id=cid, doc_id="d", text="t", score=score,
                       dense_score=score, sparse_score=score)


def test_cliff_cutoff_stops_at_drop():
    chunks = [make_chunk("a", 0.9), make_chunk("b", 0.85), make_chunk("c", 0.3), make_chunk("d", 0.28)]
    kept = cliff_cutoff(chunks, ratio=0.3)
    assert [c.chunk_id for c in kept] == ["a", "b"]


def test_cliff_cutoff_keeps_at_least_one():
    chunks = [make_chunk("a", 0.9)]
    kept = cliff_cutoff(chunks, ratio=0.3)
    assert len(kept) == 1


def test_cliff_cutoff_no_drop_keeps_all():
    chunks = [make_chunk("a", 0.9), make_chunk("b", 0.88), make_chunk("c", 0.86)]
    kept = cliff_cutoff(chunks, ratio=0.3)
    assert len(kept) == 3
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_rerank.py -v`
Expected: FAIL（AttributeError: cliff_cutoff）

- [ ] **Step 3: 在 qa_api/retriever/hybrid.py 末尾追加 cliff_cutoff**

```python
def cliff_cutoff(chunks: list[ScoredChunk], ratio: float | None = None) -> list[ScoredChunk]:
    """断崖截断：相邻分数骤降（跌幅超过 ratio）即截断。至少保留 1 条。"""
    ratio = settings.cliff_cutoff_ratio if ratio is None else ratio
    if not chunks:
        return []
    kept = [chunks[0]]
    for prev, cur in zip(chunks, chunks[1:]):
        if cur.score < prev.score * (1 - ratio):
            break
        kept.append(cur)
    return kept
```

- [ ] **Step 4: 实现 qa_api/reranker/rerank.py**

```python
"""精排：bge-reranker-large 交叉编码器；失败降级原序返回。"""
import httpx

from qa_api.retriever.hybrid import ScoredChunk
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("qa_api.reranker")


def rerank_chunks(query: str, chunks: list[ScoredChunk], client=None) -> list[ScoredChunk]:
    if not chunks:
        return chunks
    try:
        client = client or httpx.Client(timeout=settings.external_timeout)
        resp = client.post(f"{settings.rerank_service_url}/rerank",
                           json={"query": query, "documents": [c.text for c in chunks]})
        resp.raise_for_status()
        data = resp.json()
        scores = data["scores"]
        for c, s in zip(chunks, scores):
            c.score = s
        chunks.sort(key=lambda c: -c.score)
        return chunks
    except Exception as e:
        logger.warning("重排服务不可用，降级为检索原序: %s", e)
        return chunks
```

- [ ] **Step 5: 运行测试通过并提交**

Run: `uv run pytest tests/test_rerank.py -v`
Expected: PASS（3 passed）

```bash
git add qa_api/reranker/ qa_api/retriever/hybrid.py tests/test_rerank.py
git commit -m "feat: 重排模块(reranker精排+断崖截断+降级)"
```

### Task C3: 生成模块（提示词模板 + LLM 主备降级流式）

**Files:**
- Create: `qa_api/generator/__init__.py`、`qa_api/generator/prompts.py`、`qa_api/generator/llm.py`
- Test: `tests/test_llm_fallback.py`

**Interfaces:**
- Consumes: `ScoredChunk`（C1）、`shared.clients.get_llm/get_llm_backup`、`shared.config.settings`
- Produces:
  - `qa_api.generator.prompts.build_context(chunks: list[ScoredChunk]) -> str`（拼接知识片段为「[来源N] 标题（栏目·日期）：正文」格式）
  - `qa_api.generator.prompts.SYSTEM_PROMPT`（中文：只依据知识片段回答；标注 [来源N]；知识不足明说；过期片段提示"可能已过期"；禁止编造）
  - `qa_api.generator.llm.stream_answer(query: str, context: str, history: list[dict] | None = None, llm=None, backup=None) -> AsyncIterator[str]`（主 LLM 流式；异常切备；均失败抛 `ExternalServiceError`）

- [ ] **Step 1: 写失败测试 tests/test_llm_fallback.py**

```python
import pytest

from qa_api.generator.llm import stream_answer
from shared.errors import ExternalServiceError


class FakeStream:
    def __init__(self, deltas):
        self._deltas = iter(deltas)

    async def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._deltas)
        except StopIteration:
            raise StopAsyncIteration


class FakeChat:
    def __init__(self, stream):
        self._stream = stream
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        return self._stream()


class FakeCompletions:
    def __init__(self, chat):
        self.chat = chat


class FakeLLM:
    def __init__(self, stream):
        self.chat = FakeCompletions(FakeChat(stream))


class BrokenLLM(FakeLLM):
    def __init__(self):
        super().__init__(self._boom)

    def _boom(self):
        raise RuntimeError("primary down")


def chunk(delta):
    return type("C", (), {"choices": [type("Ch", (), {"delta": type("D", (), {"content": delta})()})()]})()


async def test_primary_fails_backup_used():
    primary = BrokenLLM()
    backup = FakeLLM(lambda: FakeStream([chunk("从"), chunk("备"), chunk("用")]))
    out = []
    async for delta in stream_answer("放假时间？", "ctx", llm=primary, backup=backup):
        out.append(delta)
    assert "".join(out) == "从备用"
    assert backup.chat.chat.calls == 1


async def test_both_fail_raises():
    primary = BrokenLLM()
    backup = BrokenLLM()
    with pytest.raises(ExternalServiceError):
        async for _ in stream_answer("放假时间？", "ctx", llm=primary, backup=backup):
            pass
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_llm_fallback.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 qa_api/generator/prompts.py**

```python
"""提示词模板（与逻辑分离）。"""
from qa_api.retriever.hybrid import ScoredChunk

SYSTEM_PROMPT = """你是广州大学校务智能助手，回答师生关于校务办事流程、通知公告、规章制度的问题。

规则：
1. 只能依据下方【知识片段】回答，每个关键信息后标注来源编号，如[来源1]。
2. 若知识片段不足以回答问题，明确说"知识库中暂未找到相关内容"，并给出可能的咨询方向，绝不编造。
3. 若某片段标记了"（可能已过期）"，回答时提醒用户以最新通知为准。
4. 回答用简体中文，条理清晰，先给结论再给细节。"""


def build_context(chunks: list[ScoredChunk]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        meta = f"{c.category}·{c.publish_date}" if c.publish_date else c.category
        expired_note = "（可能已过期）" if c.expired else ""
        lines.append(f"[来源{i}] {meta}{expired_note}\n{c.text}")
    return "\n\n".join(lines)
```

- [ ] **Step 4: 实现 qa_api/generator/llm.py**

```python
"""LLM 流式生成：DeepSeek 主 + DashScope 降级。"""
from typing import AsyncIterator

from qa_api.generator.prompts import SYSTEM_PROMPT
from shared.clients import get_llm, get_llm_backup
from shared.config import settings
from shared.errors import ExternalServiceError
from shared.logging import get_logger

logger = get_logger("qa_api.generator")


async def _stream_from(client, query: str, context: str, history: list[dict] | None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in (history or [])[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user",
                     "content": f"知识片段：\n{context}\n\n问题：{query}"})
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        stream=True,
        temperature=0.3,
    )
    async for part in resp:
        delta = part.choices[0].delta.content if part.choices else None
        if delta:
            yield delta


async def stream_answer(query: str, context: str, history: list[dict] | None = None,
                        llm=None, backup=None) -> AsyncIterator[str]:
    primary = llm or get_llm()
    fallback = backup or get_llm_backup()
    try:
        async for delta in _stream_from(primary, query, context, history):
            yield delta
    except Exception as e:
        logger.warning("主 LLM 失败，切降级: %s", e)
        try:
            async for delta in _stream_from(fallback, query, context, history):
                yield delta
        except Exception as e2:
            raise ExternalServiceError(f"LLM 主备均失败: {e2}") from e2
```

- [ ] **Step 5: 运行测试通过并提交**

Run: `uv run pytest tests/test_llm_fallback.py -v`
Expected: PASS（2 passed）

```bash
git add qa_api/generator/ tests/test_llm_fallback.py
git commit -m "feat: 生成模块(提示词模板+LLM主备降级流式)"
```

### Task C4: /chat SSE API + 来源引用 + 问答日志

**Files:**
- Create: `qa_api/api/__init__.py`、`qa_api/api/chat.py`
- Create: `qa_api/main.py`
- Create: `qa_api/Dockerfile`

**Interfaces:**
- Consumes: `hybrid_search/cliff_cutoff`（C1）、`rerank_chunks`（C2）、`stream_answer/build_context`（C3）
- Produces（HTTP，前端 Plan 2 依赖）:
  - `POST /api/chat` body `{"query": str, "topic": str | None, "history": [{"role","content"}]}` → SSE 事件流：
    - `event: chunk` data `{"delta": "文本增量"}`
    - `event: sources` data `{"sources": [{"doc_id","title","url","publish_date","category","expired"}]}`（生成结束后发送）
    - `event: done` data `{"query_id","elapsed_ms","answer_len"}`
    - 检索为空：`event: empty` data `{"message": "知识库中暂未找到相关内容..."}`
    - 异常：`event: error` data `{"message": "..."}`
  - `GET /api/health` → `{"status":"ok"}`
  - 问答日志写 MongoDB `qa_logs` 集合（query/answer/sources/elapsed_ms/created_at）

- [ ] **Step 1: 实现 qa_api/api/chat.py**

```python
"""问答 SSE API：检索→重排→流式生成→来源引用→日志。"""
import json
import time
import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from qa_api.generator.llm import stream_answer
from qa_api.generator.prompts import build_context
from qa_api.reranker.rerank import rerank_chunks
from qa_api.retriever.hybrid import cliff_cutoff, hybrid_search
from shared.clients import get_mongo
from shared.errors import ExternalServiceError
from shared.logging import get_logger

logger = get_logger("qa_api.chat")
router = APIRouter(prefix="/api", tags=["问答"])

EMPTY_MESSAGE = "知识库中暂未找到相关内容。建议：①换个关键词再试；②联系相关职能部门（可查官网'机构设置'栏目）；③等待系统采集最新通知后重试。"


class ChatRequest(BaseModel):
    query: str
    topic: str | None = None
    history: list[dict] | None = None


@router.post("/chat")
async def chat(req: ChatRequest):
    query_id = uuid.uuid4().hex[:12]
    started = time.monotonic()

    async def event_stream():
        try:
            chunks = await hybrid_search(req.query, topics=[req.topic] if req.topic else None)
            if not chunks:
                yield {"event": "empty", "data": json.dumps({"message": EMPTY_MESSAGE}, ensure_ascii=False)}
                return
            chunks = rerank_chunks(req.query, chunks)
            chunks = cliff_cutoff(chunks)
            answer_parts: list[str] = []

            async def generate():
                async for delta in stream_answer(req.query, build_context(chunks), req.history):
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
            elapsed_ms = int((time.monotonic() - started) * 1000)
            answer = "".join(answer_parts)
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
                                       "answer_len": len(answer)}, ensure_ascii=False)}
        except ExternalServiceError as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_stream())
```

- [ ] **Step 2: 实现 qa_api/main.py 与 Dockerfile**

```python
"""问答服务入口：FastAPI + CORS（前端 dev 跨域）。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qa_api.api import chat

app = FastAPI(title="校务中台·问答服务")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY shared ./shared
COPY qa_api ./qa_api
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" sse-starlette httpx pymilvus motor minio openai pydantic python-dotenv
ENV EMBED_SERVICE_URL=http://model-server:8001
ENV RERANK_SERVICE_URL=http://model-server:8001
EXPOSE 8003
CMD ["uvicorn", "qa_api.main:app", "--host", "0.0.0.0", "--port", "8003"]
```

- [ ] **Step 3: 冒烟验证（本地直跑）**

Run: `uv run uvicorn qa_api.main:app --port 8003`，然后：
`curl -s http://localhost:8003/api/health`
Expected: `{"status":"ok"}`
再发一条无数据提问（需 MongoDB 可达）：`curl -N -X POST http://localhost:8003/api/chat -H "Content-Type: application/json" -d '{"query":"测试"}'` → 应收到 `event: empty`

- [ ] **Step 4: 提交**

```bash
git add qa_api/
git commit -m "feat: 问答服务(/chat SSE+来源引用+问答日志)"
```

- [ ] **Step 5: 收尾——docker-compose 追加两个服务**

在 `docker-compose.yml` 的 `model-server` 服务后追加：

```yaml
  collector:
    build: ./collector
    ports: ["8002:8002"]
    environment:
      MILVUS_URI: http://milvus:19530
      MONGO_URI: mongodb://mongo:27017
      MINIO_ENDPOINT: minio:9000
      EMBED_SERVICE_URL: http://model-server:8001
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}
      DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY}
    env_file:
      - .env
    depends_on: [milvus, mongo, minio, model-server]
  qa-api:
    build: ./qa_api
    ports: ["8003:8003"]
    environment:
      MILVUS_URI: http://milvus:19530
      MONGO_URI: mongodb://mongo:27017
      EMBED_SERVICE_URL: http://model-server:8001
      RERANK_SERVICE_URL: http://model-server:8001
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}
      DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY}
    env_file:
      - .env
    depends_on: [milvus, mongo, model-server]
```

```bash
git add docker-compose.yml
git commit -m "feat: compose追加collector与qa-api服务"
```




---
