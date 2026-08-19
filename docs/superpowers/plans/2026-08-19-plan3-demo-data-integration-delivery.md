# Plan 3：模拟数据·集成测试·打包交付 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **派活约定（ADR-011）**：D/E 阶段后端任务（D1~D3、E1~E2）由主会话（deepseek-v4-pro）用 `workflow` 批量派发给 `model: 'glm-5.3'`，任务简报即本计划 Task 章节（自包含：文件/接口/验收/测试代码）。E1 集成测试的**真环境跑通验证由主会话执行**（子代理报告≠通过）。F1~F3 由主会话直接执行（容器编排/文档/验收）。

**Goal:** 补齐交付三件套：① 六大专题域模拟数据播种脚本（演示知识库不空、可复现）；② 集成测试（mock 站点全链路真存储真跑、降级路径、幂等）与评审遗留测试（B7 调度器注册、B8 tasks API、collector `/health`）；③ 打包交付（前端容器化进 compose 实现「一条 `docker compose up` 起全栈」、20 题演示清单、作品说明书与演示视频脚本）。同时修复打标质量（规则词表扩充，真实采集不再专题为空）。

**Architecture:** 模拟数据以**内置模板语料**（确定性、离线可复现，用户已拍板）生成 `ParsedArticle`，走真实 `classify_category → rule_tag_topics → infer_expiry → ingest_document` 管线三写入库，幂等可重跑。集成测试用 `httpx.MockTransport` 假站点（spec §9.1 的「mock 站点」）+ 真实下游（解析/打标/时效/向量化/Milvus/Mongo/MinIO/检索/问答），专用集合 `school_docs_it` 隔离、前后清理，**直接真跑存储**（用户已拍板，存储与 model_server 必须在线）。前端构建产物用 nginx 容器进 compose，代理 `/admin-api→collector`、`/qa-api→qa-api`（SSE 关闭缓冲），与 vite dev 代理语义一致。

**Tech Stack:** Python 3.11 / uv / pytest(-asyncio) / httpx(MockTransport+ASGITransport) / motor / pymilvus / minio / openai SDK（stub 降级测试）/ Docker / nginx / pnpm。

**Spec:** `docs/superpowers/specs/2026-08-18-school-knowledge-hub-design.md`（§9 测试策略、§12 阶段 E/F、硬约束 2）+ `docs/adr/ADR-010`（模拟数据策略）。执行者必读。

## Global Constraints

- 服务间不互相调用业务逻辑，只通过 HTTP API 与共享存储通信（spec §4）。
- 降级铁律：可选依赖失败不得拖垮主链路（spec §8）——本计划的降级测试即验证该契约。
- 幂等铁律：同一采集任务/播种脚本重复跑不产生重复数据（spec §8）。
- 密钥纪律：`.env` 不进 git；测试/脚本不硬编码密钥。
- 中文：日志/注释/测试命名/提交信息均用中文。
- **前置条件（E 阶段真跑）**：docker 存储在线（Milvus `localhost:19530`、Mongo `localhost:27017`、MinIO `localhost:9000`）+ `model_server` 起在 `8001`（embed/rerank 真跑）。DSH 沙箱起服务需先注入用户级密钥：`$env:DEEPSEEK_API_KEY=[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')`（PROGRESS.md 已记录该环境事实）。LLM 问答段在无 key 时跳过（skip），不视为测试失败。
- transformers 锁 4.52.x（5.x 破坏 FlagEmbedding）；Milvus dense 索引用 AUTOINDEX（小数数据 IVF 空召回，勿回退）。
- YAGNI：不做 RAGAS 评测、登录权限、多租户（spec §11）。

## File Structure（本计划创建/修改的文件）

```
collector/main.py                        [改] 追加 GET /api/health
collector/tagger/rules.py                [改] 扩充规则词表 + TOPIC_KEYWORDS + rule_tag_topics
collector/tasks.py                       [改] 专题打标规则兜底（LLM 无结果时）
scripts/__init__.py                      [新] 空文件（-m scripts.seed_demo 可导入）
scripts/demo_templates.py                [新] 六大专题域 18 篇内置模板语料
scripts/seed_demo.py                     [新] 播种主脚本（幂等、MinIO bucket 确保）
tests/test_admin_api.py                  [新] collector /health + tasks API 测试（B8 遗留）
tests/test_scheduler.py                  [新] 调度器注册测试（B7 遗留）
tests/test_topic_rules.py                [新] 专题规则词表 + 任务兜底测试
tests/test_seed_templates.py             [新] 模板完整性/一致性测试
tests/test_degradation.py                [新] 降级路径测试（reranker/LLM 主备）
tests/integration/test_full_pipeline.py  [新] 全链路集成测试（真存储，marker=integration）
pyproject.toml                           [改] 注册 integration marker
frontend/Dockerfile                      [新] pnpm build → nginx 两段构建
frontend/nginx.conf                      [新] SPA fallback + /admin-api、/qa-api 代理（SSE 关闭缓冲）
docker-compose.yml                       [改] 追加 frontend 服务（5173:80）
README.md                                [改] 快速开始改为一条 compose 起全栈 + 播种命令
docs/demo/20-questions.md                [新] 20 题演示问题清单（含期望来源）
docs/作品说明书.md                        [新] 大赛作品说明书
docs/演示视频脚本.md                      [新] 演示视频分镜脚本
docs/PROGRESS.md                         [改] 进度同步（F3 收尾）
```

---

## 阶段 D：演示数据与质量补强

### Task D1: collector 服务级补全（/health + 调度器注册测试 + tasks API 测试）

**Files:**
- Create: `tests/test_admin_api.py`
- Create: `tests/test_scheduler.py`
- Modify: `collector/main.py`（追加 health 端点）

**Interfaces:**
- Produces: `GET /api/health` → `{"status": "ok"}`（200）；qa_api 已有同名端点（`qa_api/main.py:17`），collector 对齐该形状，供 nginx/健康检查使用。
- Consumes: 现有 `collector.scheduler.start_scheduler/stop_scheduler`（`collector/scheduler.py:13`）、`collector.api.tasks` 路由（前缀 `/api/admin/tasks`）。

- [ ] **Step 1: 写测试（health 预期失败，其余是补回归测试）**

```python
# tests/test_admin_api.py
"""collector 管理端 API 测试：/health + 任务触发/查询（B8 评审遗留补齐）。"""
import asyncio

import httpx
import pytest

from collector.api import tasks as tasks_api
from collector.main import app
from collector.sources import SourceConfig


@pytest.fixture
async def client():
    # ASGITransport 不跑 lifespan → 调度器不启动、不触 Mongo
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_collector_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_trigger_run_creates_task(client, monkeypatch):
    source = SourceConfig(id="s1", name="主站公告", list_url="https://www.gzhu.edu.cn/z__l/tzgg.htm",
                          adapter="gzhu", enabled=True, interval_minutes=60)
    async def fake_list_all():
        return [source]
    monkeypatch.setattr("collector.sources.list_all_sources", fake_list_all)
    ran = []
    async def fake_run(s):
        ran.append(s.id)
        return {"task_id": "t1", "status": "running"}
    monkeypatch.setattr(tasks_api, "run_collection_task", fake_run)
    resp = await client.post("/api/admin/tasks/s1/run")
    assert resp.status_code == 200
    assert resp.json() == {"started": True, "source_id": "s1"}
    await asyncio.sleep(0)  # 让 create_task 的协程执行
    assert ran == ["s1"]


async def test_trigger_run_unknown_source(client, monkeypatch):
    async def fake_list_all():
        return []
    monkeypatch.setattr("collector.sources.list_all_sources", fake_list_all)
    resp = await client.post("/api/admin/tasks/nope/run")
    assert resp.status_code == 200
    assert resp.json() == {"error": "采集源不存在"}


async def test_list_tasks(client, monkeypatch):
    class FakeCursor:
        def __init__(self, items):
            self._items = items
        def sort(self, *a, **k):
            return self
        def limit(self, n):
            return self
        def __aiter__(self):
            self._it = iter(self._items)
            return self
        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    class FakeTasksColl:
        def find(self, query):
            return FakeCursor([{"task_id": "t1", "source_id": "s1", "status": "success"}])

    class FakeDb:
        def __getitem__(self, name):
            return FakeTasksColl()

    monkeypatch.setattr(tasks_api, "get_mongo", lambda: FakeDb())
    resp = await client.get("/api/admin/tasks?source_id=s1")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1 and items[0]["task_id"] == "t1"
```

```python
# tests/test_scheduler.py
"""调度器装配测试（B7 评审遗留补齐）：enabled 采集源注册周期任务。"""
from collector import scheduler as sched_mod
from collector.sources import SourceConfig


async def test_start_scheduler_registers_enabled_sources(monkeypatch):
    source = SourceConfig(id="s1", name="主站公告", list_url="https://www.gzhu.edu.cn/z__l/tzgg.htm",
                          adapter="gzhu", enabled=True, interval_minutes=360)
    async def fake_list_sources():
        return [source]
    monkeypatch.setattr(sched_mod, "list_sources", fake_list_sources)
    try:
        await sched_mod.start_scheduler()
        jobs = sched_mod._scheduler.get_jobs()
        assert any(j.id == f"collect-{source.id}" for j in jobs)
    finally:
        sched_mod.stop_scheduler()


async def test_start_scheduler_second_call_is_noop(monkeypatch):
    async def fake_list_sources():
        return []
    monkeypatch.setattr(sched_mod, "list_sources", fake_list_sources)
    try:
        await sched_mod.start_scheduler()
        first = sched_mod._scheduler
        await sched_mod.start_scheduler()
        assert sched_mod._scheduler is first  # 幂等，不重复装配
    finally:
        sched_mod.stop_scheduler()
```

- [ ] **Step 2: 跑测试确认失败/通过状态**

Run: `uv run pytest tests/test_admin_api.py::test_collector_health tests/test_admin_api.py::test_list_tasks -v`
Expected: `test_collector_health` FAIL（404：/api/health 不存在）；`test_list_tasks` PASS（B8 已有功能，回归测试直接绿）。

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: PASS（B7 已有功能，回归测试直接绿）。

- [ ] **Step 3: 实现 /health**

`collector/main.py` 在 `include_router` 三行之后追加：

```python
@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: 全量跑通**

Run: `uv run pytest tests/test_admin_api.py tests/test_scheduler.py -v`
Expected: 6 passed。

- [ ] **Step 5: Commit**

```bash
git add collector/main.py tests/test_admin_api.py tests/test_scheduler.py
git commit -m "feat: collector补/health端点+调度器注册与tasks API自动化测试(B7/B8遗留)"
```

---

### Task D2: 打标规则词表扩充 + 专题域规则兜底（修复真实采集专题为空）

**背景**：联调发现 8 篇真实 gzhu 采集全部 fallback「通知公告」（栏目映射所致，属正常）但**专题全部为空**（当时 LLM 缺 key、且无规则兜底）。本任务补：① 一级分类词表扩充；② 专题域关键词规则 `rule_tag_topics`；③ 任务管线在 LLM 打标无结果时用规则兜底。

**Files:**
- Modify: `collector/tagger/rules.py`
- Modify: `collector/tasks.py`（打标兜底一行）
- Create: `tests/test_topic_rules.py`

**Interfaces:**
- Produces: `rule_tag_topics(title: str, content: str) -> list[str]`——按 `TOPIC_KEYWORDS` 匹配，返回命中的专题域列表（可多个、可空）；专题域词表与 `collector.tagger.llm_topics.TOPICS` 一致。
- Consumes: `collector.tagger.llm_topics.TOPICS`（六大专题域常量）、`collector/tasks.py:63-69` 打标循环。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_topic_rules.py
"""专题域规则打标测试 + 任务管线规则兜底测试。"""
from unittest.mock import AsyncMock

import pytest

from collector import tasks as tasks_mod
from collector.crawler.base import RawArticle
from collector.parser.extract import ParsedArticle
from collector.sources import SourceConfig
from collector.tagger.rules import rule_tag_topics


def test_topic_rules_match_keywords():
    assert "新生入学" in rule_tag_topics("关于2026级新生入学报到安排的通知", "新生报到时间与流程如下")
    assert "教务学籍" in rule_tag_topics("本学期选课安排", "学生登录教务系统选课")


def test_topic_rules_multi_and_empty():
    got = rule_tag_topics("港澳台学生学籍管理办法", "港澳台学生学籍注册与内地学生同等管理")
    assert "港澳生服务" in got and "教务学籍" in got
    assert rule_tag_topics("某条无关标题", "没有任何关键词的内容") == []


async def test_task_topics_fallback_to_rules_when_llm_empty(monkeypatch):
    """LLM 打标返回空（缺 key/失败）时，专题用规则兜底，不再为空。"""
    fake_engine = AsyncMock()
    fake_engine.fetch_source = AsyncMock(return_value=(
        [RawArticle(url="https://x/1.htm", title="关于新生入学宿舍申请的通知", html="<html>x</html>",
                    publish_date="2026-08-10", source_site="gzhu", column="通知公告")], []))
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: fake_engine)
    fake_mongo = AsyncMock()
    fake_mongo.insert_one = AsyncMock()
    fake_mongo.update_one = AsyncMock()
    fake_mongo.__getitem__.return_value = fake_mongo
    monkeypatch.setattr(tasks_mod, "get_mongo", lambda: fake_mongo)

    def fake_extract(raw):
        return ParsedArticle(url=raw.url, title=raw.title,
                             content="新生入学宿舍申请流程说明，请按通知办理", publish_date=raw.publish_date,
                             department=None, source_site=raw.source_site, column=raw.column, raw_html=raw.html)
    monkeypatch.setattr(tasks_mod, "extract_article", fake_extract)
    monkeypatch.setattr(tasks_mod, "batch_tag_topics", AsyncMock(return_value={}))  # LLM 无结果
    ingested = []
    async def fake_ingest(parsed, category, topics, expire_at):
        ingested.append((category, topics))
    monkeypatch.setattr("collector.ingest.writer.ingest_document", fake_ingest)

    source = SourceConfig(id="s1", name="主站公告", list_url="https://x/list.htm",
                          adapter="gzhu", enabled=True, interval_minutes=60)
    result = await tasks_mod.run_collection_task(source)
    assert result["status"] == "success"
    assert any("新生入学" in topics for _, topics in ingested)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_topic_rules.py -v`
Expected: FAIL——`rule_tag_topics` 未定义（ImportError）。

- [ ] **Step 3: 实现规则词表与兜底**

`collector/tagger/rules.py` 全文替换为：

```python
"""一级分类 + 专题域：规则打标（来源栏目映射 + 标题/正文关键词）。"""
from collector.tagger.llm_topics import TOPICS

CATEGORIES = ["通知公告", "办事指南", "规章制度", "新闻动态"]

RULE_KEYWORDS = {
    "通知公告": ["通知", "公告", "公示", "通告", "安排", "报名", "评选", "征集", "招标"],
    "办事指南": ["指南", "流程", "办事", "办理", "申请", "须知", "攻略", "指引"],
    "规章制度": ["规定", "办法", "制度", "条例", "细则", "章程", "规范", "守则"],
}

COLUMN_TO_CATEGORY = {
    "通知公告": "通知公告",
    "新闻动态": "新闻动态",
}

# 专题域关键词（与 llm_topics.TOPICS 一一对应）；规则兜底用，多选可命中多个
TOPIC_KEYWORDS = {
    "新生入学": ["新生", "入学", "报到", "迎新", "军训"],
    "港澳生服务": ["港澳", "港澳台", "香港", "澳门"],
    "教务学籍": ["学籍", "选课", "转专业", "学分", "成绩", "考试", "教务"],
    "后勤生活": ["宿舍", "食堂", "校园卡", "后勤", "公寓", "卡务", "水电"],
    "就业创业": ["就业", "招聘", "创业", "简历", "实习"],
    "科研学术": ["科研", "学术", "实验室", "论文", "课题", "基金"],
}


def classify_category(title: str, column: str) -> str:
    """栏目映射优先；其次标题关键词；兜底新闻动态。"""
    if column in COLUMN_TO_CATEGORY:
        return COLUMN_TO_CATEGORY[column]
    for category, words in RULE_KEYWORDS.items():
        if any(w in title for w in words):
            return category
    return "新闻动态"


def rule_tag_topics(title: str, content: str) -> list[str]:
    """专题域规则打标：标题+正文关键词命中即标；LLM 打标失败/无结果时的兜底。"""
    text = title + " " + content
    return [topic for topic in TOPICS if any(w in text for w in TOPIC_KEYWORDS[topic])]
```

`collector/tasks.py` 打标循环（约 65-69 行）改为：

```python
    topics_map = await batch_tag_topics(parsed)
    succeeded = 0
    for art in parsed:
        try:
            category = classify_category(art.title, art.column)
            topics = topics_map.get(art.url) or rule_tag_topics(art.title, art.content)
            expire_at = infer_expiry(art.title, art.content, category, art.publish_date or "")
            await ingest_document(art, category, topics, expire_at)
```

同文件顶部 import 补一行：

```python
from collector.tagger.rules import classify_category, rule_tag_topics
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_topic_rules.py tests/test_tagger.py -v`
Expected: 全部 PASS（既有 test_tagger 不受影响）。

- [ ] **Step 5: Commit**

```bash
git add collector/tagger/rules.py collector/tasks.py tests/test_topic_rules.py
git commit -m "feat: 打标规则词表扩充+专题域规则兜底(LLM无结果不再专题为空)"
```

- [ ] **Step 6: 复采验证（主会话真环境执行）**

```powershell
# 起 collector（需注入密钥；无 key 也不影响——规则兜底不依赖 LLM）
uv run uvicorn collector.main:app --port 8002
# 对既有采集源触发复采（源 id 以实际为准，历史为 f1bfb927f134）
curl -X POST http://127.0.0.1:8002/api/admin/tasks/f1bfb927f134/run
# 稍候查专题是否非空（用 uv 跑一段 Python 查询）
uv run python -c "import asyncio; from motor.motor_asyncio import AsyncIOMotorClient; async def m(): db=AsyncIOMotorClient('mongodb://localhost:27017')['school_knowledge_hub']; docs=[d async for d in db['documents'].find({'source_site':'gzhu'})]; print('专题非空篇数:', sum(1 for d in docs if d.get('topics'))); print('样例:', [(d['title'][:18], d['topics']) for d in docs[:3]]); asyncio.run(m())"
```
Expected: 「专题非空篇数」> 0（修复前为 0）。

---

### Task D3: 模拟数据播种脚本（六大专题域内置模板，幂等可重跑）

**背景（ADR-010）**：演示环境 = 真实采集数据 + 模拟数据共同入库。内置模板语料（用户已拍板）：确定性、离线可复现、零 API 依赖。每篇走真实分类/打标/时效/入库管线，保证与真实采集数据同构同链路。

**Files:**
- Create: `scripts/__init__.py`（空文件）
- Create: `scripts/demo_templates.py`
- Create: `scripts/seed_demo.py`
- Create: `tests/test_seed_templates.py`

**Interfaces:**
- Produces: `scripts.demo_templates.DemoTemplate`（dataclass：`topic/category/column/title/content/publish_date/department`）与 `DEMO_ARTICLES: list[DemoTemplate]`（18 篇，六大专题域各 3 篇）；`scripts.seed_demo.seed_all() -> int`（返回播种篇数，幂等）。
- Consumes: `collector.tagger.rules.classify_category/rule_tag_topics`（D2）、`collector.lifecycle.validity.infer_expiry`、`collector.ingest.writer.ingest_document`、`collector.parser.extract.ParsedArticle`。
- 文档 URL 约定：`https://demo.gzhu.edu.cn/demo/{i+1:02d}.htm`（i 为模板下标）→ doc_id = md5(url)[:16] 稳定不变，重跑即先删后插。

- [ ] **Step 1: 写失败测试（模板一致性）**

```python
# tests/test_seed_templates.py
"""模拟数据模板库测试：六大专题域全覆盖、字段完整、与规则词表一致。"""
from collector.tagger.llm_topics import TOPICS
from collector.tagger.rules import CATEGORIES, classify_category, rule_tag_topics
from scripts.demo_templates import DEMO_ARTICLES


def test_templates_cover_all_six_topics():
    assert {t.topic for t in DEMO_ARTICLES} == set(TOPICS)


def test_each_topic_has_at_least_three_articles():
    for topic in TOPICS:
        assert sum(1 for t in DEMO_ARTICLES if t.topic == topic) >= 3


def test_templates_valid_and_consistent_with_rules():
    assert len(DEMO_ARTICLES) >= 18
    urls = set()
    for t in DEMO_ARTICLES:
        assert t.title and len(t.content) >= 50, f"{t.title} 正文过短"
        assert t.topic in TOPICS and t.category in CATEGORIES
        assert t.publish_date and t.department and t.column
        # 规则必须把模板归到其声明分类（保证播种管线产出确定性）
        assert classify_category(t.title, t.column) == t.category, f"{t.title} 分类不一致"
        # 规则必须命中其声明专题（保证专题非空）
        assert t.topic in rule_tag_topics(t.title, t.content), f"{t.title} 专题不一致"
        # filename 唯一
        filename = f"{t.topic}-{t.title[:8]}"
        assert filename not in urls
        urls.add(filename)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_seed_templates.py -v`
Expected: FAIL——`scripts.demo_templates` 模块不存在（ModuleNotFoundError）。

- [ ] **Step 3: 实现模板库与播种脚本**

`scripts/__init__.py`：

```python
# scripts 包：演示数据播种（uv run python -m scripts.seed_demo）
```

`scripts/demo_templates.py`：

```python
"""六大专题域演示模板语料（内置、确定性；标题/正文均含分类与专题关键词，与规则词表一致）。"""
from dataclasses import dataclass


@dataclass
class DemoTemplate:
    topic: str
    category: str
    column: str
    title: str
    content: str
    publish_date: str
    department: str


DEMO_ARTICLES: list[DemoTemplate] = [
    # ===== 新生入学 =====
    DemoTemplate("新生入学", "通知公告", "通知公告", "关于2026级新生入学报到安排的通知",
                 "2026级新生报到时间为9月1日至9月2日，报到地点为各学院迎新点。新生须携带录取通知书、身份证办理报到手续。报到当天学校在火车站、机场设迎新接站点，可免费乘坐迎新专车到校。未按时报到的新生须提前向所在学院请假。", "2026-08-15", "学生处"),
    DemoTemplate("新生入学", "办事指南", "办事指南", "新生办理校园卡指南",
                 "新生入学后凭校园卡办理宿舍门禁与食堂消费。办理流程：登录校园卡服务大厅提交申请，上传一寸免冠照片，审核通过后到卡务中心领取。校园卡初始密码为身份证后六位，请及时修改。", "2026-08-12", "后勤服务处"),
    DemoTemplate("新生入学", "通知公告", "通知公告", "2026级新生军训时间安排的通知",
                 "2026级新生军训定于9月3日至9月16日进行，共14天。新生须于9月3日上午8时到田径场集合。军训期间实行封闭管理，请新生提前准备防晒用品与运动鞋。", "2026-08-14", "武装部"),
    # ===== 港澳生服务 =====
    DemoTemplate("港澳生服务", "办事指南", "办事指南", "港澳台学生入学注册办理流程",
                 "港澳台学生入学注册流程：第一步到港澳台事务办公室核验通行证与录取通知书，第二步到学院报到，第三步办理住宿登记。注册时间为9月1日至9月2日，逾期须提前联系港澳台事务办公室。", "2026-08-10", "港澳台事务办公室"),
    DemoTemplate("港澳生服务", "通知公告", "通知公告", "关于港澳学生住宿安排的通知",
                 "经研究，2026级港澳学生统一安排在大学城校区港澳生公寓。港澳学生可于8月30日起办理入住，入住时需出示港澳居民来往内地通行证。", "2026-08-11", "学生公寓管理中心"),
    DemoTemplate("港澳生服务", "规章制度", "规章制度", "港澳台学生学籍管理办法",
                 "为规范港澳台学生学籍管理，制定本办法。港澳台学生学籍注册、课程修读、成绩记载与内地学生同等管理。休学、复学按学校学籍管理规定办理。本办法自发布之日起施行。", "2026-08-05", "教务处"),
    # ===== 教务学籍 =====
    DemoTemplate("教务学籍", "办事指南", "办事指南", "学生转专业申请办理指南",
                 "学生转专业申请办理流程：符合条件的学生在每学年第二学期开学初提交转专业申请，经转入学院考核、教务处审批后公示。转专业结果在教务系统公布，学生可登录查询。", "2026-08-08", "教务处"),
    DemoTemplate("教务学籍", "通知公告", "通知公告", "2026-2027学年第一学期选课安排通知",
                 "2026-2027学年第一学期选课分三轮进行：第一轮预选、第二轮正选、第三轮补退选。学生须登录教务系统按时完成选课，逾期不再受理。选课期间系统开放时间为每日8:00-22:00。", "2026-08-18", "教务处"),
    DemoTemplate("教务学籍", "规章制度", "规章制度", "本科生学籍管理规定",
                 "为维护正常教学秩序，规范本科生学籍管理，制定本规定。本科标准学制为四年，最长学习年限六年。学生应按培养方案修读课程并取得规定学分，成绩不合格须参加重修。", "2026-08-02", "教务处"),
    # ===== 后勤生活 =====
    DemoTemplate("后勤生活", "办事指南", "办事指南", "学生宿舍调换申请流程",
                 "学生宿舍调换申请流程：学生提交调宿申请，经辅导员审核、公寓管理中心审批后办理。调宿一般在每学期开学初集中办理，特殊情况可随时申请。", "2026-08-09", "学生公寓管理中心"),
    DemoTemplate("后勤生活", "通知公告", "通知公告", "关于暑假期间食堂开放时间的通知",
                 "暑假期间各校区食堂开放安排如下：大学城校区第一食堂正常供餐，桂花岗校区第二食堂供餐至8月15日。供餐时间为早餐7:00-9:00、午餐11:00-13:00、晚餐17:00-19:00。", "2026-08-01", "后勤服务处"),
    DemoTemplate("后勤生活", "办事指南", "办事指南", "校园卡补办办理须知",
                 "校园卡遗失后请及时挂失并补办。补办流程：登录校园卡服务大厅挂失，持身份证到卡务中心缴费补卡，新卡立等可取。补卡后原卡余额自动转入新卡。", "2026-08-06", "卡务中心"),
    # ===== 就业创业 =====
    DemoTemplate("就业创业", "通知公告", "通知公告", "2026届毕业生秋季校园招聘会安排通知",
                 "学校定于9月20日在大学城校区举办2026届毕业生秋季校园招聘会，参会企业200余家。毕业生请提前登录就业信息网完善简历，凭学生证入场。", "2026-08-13", "就业指导中心"),
    DemoTemplate("就业创业", "办事指南", "办事指南", "大学生创业项目申报流程指南",
                 "大学生创业项目申报流程：学生团队提交项目申报书，经学院初审、学校评审后立项。立项项目可获得启动资金与孵化场地支持。申报时间：每学年第一学期。", "2026-08-07", "创新创业学院"),
    DemoTemplate("就业创业", "新闻动态", "新闻动态", "就业指导中心举办简历制作讲座",
                 "9月12日下午，就业指导中心邀请人力资源专家举办简历制作讲座，200余名学生参加。讲座围绕简历结构、亮点挖掘与求职礼仪展开，现场互动热烈。", "2026-08-16", "就业指导中心"),
    # ===== 科研学术 =====
    DemoTemplate("科研学术", "通知公告", "通知公告", "关于2026年度校级科研项目申报的通知",
                 "2026年度校级科研项目申报工作现已启动。项目类别包括重点项目、一般项目与青年项目。申请人须于9月30日前通过科研管理系统提交申报书。", "2026-08-04", "科研处"),
    DemoTemplate("科研学术", "新闻动态", "新闻动态", "我校学者在国际学术期刊发表高水平论文",
                 "近日，我校材料学院课题组在材料科学领域国际学术期刊发表研究论文，报道了新型储能材料的重要进展。该研究获国家自然科学基金资助。", "2026-08-17", "科研处"),
    DemoTemplate("科研学术", "办事指南", "办事指南", "实验室安全准入培训办理指南",
                 "进入实验室须先完成安全准入培训。办理流程：在线学习安全课程并参加考试，成绩合格后签订安全承诺书，领取准入卡。培训每学期集中组织一次。", "2026-08-03", "实验室与设备管理处"),
]
```

`scripts/seed_demo.py`：

```python
"""演示模拟数据播种：六大专题域模板 → 真实分类/打标/时效/三写入库管线（幂等可重跑）。

用法：uv run python -m scripts.seed_demo
前置：docker 存储（Milvus/Mongo/MinIO）+ model_server:8001 在线。
"""
import asyncio

from collector.ingest.writer import ingest_document
from collector.lifecycle.validity import infer_expiry
from collector.parser.extract import ParsedArticle
from collector.tagger.rules import classify_category, rule_tag_topics
from scripts.demo_templates import DEMO_ARTICLES
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("scripts.seed_demo")


def _ensure_bucket(minio=None) -> None:
    """MinIO 桶不存在则创建（空环境首次运行必需）；失败仅告警不阻断。"""
    from shared.clients import get_minio

    try:
        m = minio or get_minio()
        if not m.bucket_exists(settings.minio_bucket):
            m.make_bucket(settings.minio_bucket)
    except Exception as e:
        logger.warning("MinIO 桶检查失败(降级): %s", e)


async def seed_all() -> int:
    _ensure_bucket()
    for i, t in enumerate(DEMO_ARTICLES):
        url = f"https://demo.gzhu.edu.cn/demo/{i + 1:02d}.htm"
        parsed = ParsedArticle(
            url=url, title=t.title, content=t.content, publish_date=t.publish_date,
            department=t.department, source_site="demo", column=t.column,
            raw_html=(f"<html><head><title>{t.title}</title></head><body>"
                      f"<h1>{t.title}</h1><div class='content'>{t.content}</div></body></html>"),
        )
        category = classify_category(t.title, t.column)
        topics = rule_tag_topics(t.title, t.content) or [t.topic]
        expire_at = infer_expiry(t.title, t.content, category, t.publish_date)
        await ingest_document(parsed, category, topics, expire_at)
        logger.info("已播种 [%s] %s", t.topic, t.title)
    return len(DEMO_ARTICLES)


async def demo_doc_count() -> int:
    from shared.clients import get_mongo

    db = get_mongo()
    n = 0
    async for _ in db["documents"].find({"url": {"$regex": "^https://demo.gzhu.edu.cn/demo/"}}):
        n += 1
    return n


if __name__ == "__main__":
    seeded = asyncio.run(seed_all())
    print(f"播种完成：{seeded} 篇；库内演示文档总数：{asyncio.run(demo_doc_count())}")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_seed_templates.py -v`
Expected: 3 passed（模板与规则完全一致）。

- [ ] **Step 5: Commit**

```bash
git add scripts/ tests/test_seed_templates.py
git commit -m "feat: 六大专题域模拟数据播种脚本(内置模板18篇,幂等可重跑)"
```

- [ ] **Step 6: 真环境播种验证（主会话执行；前置：存储 + model_server:8001 在线）**

```powershell
uv run python -m scripts.seed_demo        # 第一次：播种完成：18 篇
uv run python -m scripts.seed_demo        # 第二次：仍 18 篇（幂等先删后插，不重复）
```
Expected: 两次输出均「播种完成：18 篇；库内演示文档总数：18」。

---

## 阶段 E：集成测试（真跑存储）

> **前置条件（每次运行前确认）**：docker 存储在线 + `uv run uvicorn model_server.main:app --port 8001` 已起。全量测试命令：`uv run pytest tests/ -v`；纯单测快速通道：`uv run pytest tests/ -m "not integration" -v`（用户拍板「直接真跑存储」：集成测试不提供 mock 存储模式）。

### Task E1: 全链路集成测试（mock 站点 → 采集 → 入库 → 检索 → 问答 → 来源引用；幂等两遍）

**Files:**
- Create: `tests/integration/test_full_pipeline.py`
- Modify: `pyproject.toml`（注册 integration marker）

**Interfaces:**
- Consumes: `collector.tasks.run_collection_task`（D2 后专题有规则兜底）、`collector.ingest.writer.doc_id_of`、`qa_api.retriever.hybrid.hybrid_search`、`qa_api.generator.llm.stream_answer`、`qa_api.generator.prompts.build_context`、`shared.clients.get_milvus/get_mongo/get_minio`。
- 隔离约定：Milvus 用专用集合 `school_docs_it`（monkeypatch `settings.milvus_collection`，前后 drop）；Mongo 测试文档以 URL 前缀 `https://demo.it/` 识别清理；MinIO 按测试 doc_id 精确清理快照。不触碰演示库 `school_docs`。

- [ ] **Step 1: 写失败测试 + marker 注册**

`pyproject.toml` 的 `[tool.pytest.ini_options]` 段追加一行：

```toml
markers = ["integration: 需要 docker 存储与 model_server 在线的集成测试"]
```

```python
# tests/integration/test_full_pipeline.py
"""全链路集成测试（真存储真跑）：mock 站点 → 采集 → 解析打标 → 三写入库 → 混合检索 → 问答来源。

前置：Milvus/Mongo/MinIO 在线 + model_server:8001 在线；LLM 问答段无 DEEPSEEK_API_KEY 时跳过。
运行：uv run pytest tests/integration -v
"""
import httpx
import pytest

from collector import tasks as tasks_mod
from collector.crawler.engine import CrawlEngine
from collector.ingest.writer import doc_id_of
from collector.sources import SourceConfig
from qa_api.retriever.hybrid import hybrid_search
from shared.clients import get_milvus, get_minio, get_mongo
from shared.config import settings

pytestmark = pytest.mark.integration

COLLECTION = "school_docs_it"
SOURCE_ID = "it-src"
PREFIX = "https://demo.it/"

# 5 篇 mock 站点文章：标题含分类/专题关键词（D2 规则兜底出专题，不依赖 LLM）
DETAILS = {
    "https://demo.it/info/1.htm": ("关于新生入学宿舍申请的通知", "2026-08-10",
                                   "新生入学宿舍申请流程：学生登录公寓系统提交申请，经辅导员审核、公寓管理中心审批后安排入住。新生报到期间可现场办理。"),
    "https://demo.it/info/2.htm": ("学生转专业申请办理指南", "2026-08-08",
                                   "学生转专业申请办理流程：每学年第二学期开学初提交申请，经转入学院考核、教务处审批后公示，结果在教务系统公布。"),
    "https://demo.it/info/3.htm": ("关于2026年度校级科研项目申报的通知", "2026-08-04",
                                   "2026年度校级科研项目申报现已启动，项目类别包括重点项目、一般项目与青年项目，申请人须于9月30日前通过科研管理系统提交申报书。"),
    "https://demo.it/info/4.htm": ("校园卡补办办理须知", "2026-08-06",
                                   "校园卡遗失后请及时挂失并补办。补办流程：登录校园卡服务大厅挂失，持身份证到卡务中心缴费补卡，补卡后余额自动转入新卡。"),
    "https://demo.it/info/5.htm": ("2026届毕业生秋季校园招聘会安排通知", "2026-08-13",
                                   "学校定于9月20日举办2026届毕业生秋季校园招聘会，参会企业200余家。毕业生请提前登录就业信息网完善简历，凭学生证入场。"),
}


def mock_site_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/list.htm":
        items = "".join(
            f'<li><a href="/info/{i}.htm" title="{title}"><span>{date}</span></a></li>'
            for i, (url, (title, date, _)) in enumerate(DETAILS.items(), 1))
        return httpx.Response(200, text=f"<html><body><ul>{items}</ul></body></html>")
    for url, (title, date, content) in DETAILS.items():
        if request.url.path in url:
            return httpx.Response(200, text=(
                f"<html><head><title>{title}</title></head><body><h1>{title}</h1>"
                f"<p class='date'>发布时间：{date}</p><div class='content'>{content}</div></body></html>"))
    return httpx.Response(404, text="not found")


def make_source() -> SourceConfig:
    return SourceConfig(id=SOURCE_ID, name="集成测试源", list_url=f"{PREFIX}list.htm",
                        adapter="gzhu", enabled=True, interval_minutes=60)


def make_engine() -> CrawlEngine:
    return CrawlEngine(http_client=httpx.AsyncClient(transport=httpx.MockTransport(mock_site_handler)))


@pytest.fixture(autouse=True)
async def isolated_storage(monkeypatch):
    monkeypatch.setattr(settings, "milvus_collection", COLLECTION)
    milvus = get_milvus()
    if milvus.has_collection(COLLECTION):
        milvus.drop_collection(COLLECTION)
    yield
    # 清理：Milvus 集合 / Mongo 测试文档与任务 / MinIO 测试快照
    if milvus.has_collection(COLLECTION):
        milvus.drop_collection(COLLECTION)
    db = get_mongo()
    await db["documents"].delete_many({"url": {"$regex": "^https://demo.it/"}})
    await db["task_runs"].delete_many({"source_id": SOURCE_ID})
    try:
        keys = [f"snapshots/{doc_id_of(u)}.html" for u in DETAILS]
        list(get_minio().remove_objects(settings.minio_bucket, keys))
    except Exception:
        pass  # 桶不存在或快照缺省（降级路径）时忽略


async def test_full_pipeline_collect_retrieve_answer(monkeypatch):
    """mock 站点 5 篇 → 真实采集入库 → 真实混合检索 → 来源引用 → (有 key 时)真实 LLM 问答。"""
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: make_engine())
    result = await tasks_mod.run_collection_task(make_source())
    assert result["status"] == "success" and result["succeeded"] == len(DETAILS)

    db = get_mongo()
    docs = [d async for d in db["documents"].find({"url": {"$regex": "^https://demo.it/"}})]
    assert len(docs) == len(DETAILS)
    assert all(d["topics"] for d in docs)  # D2 规则兜底：专题非空

    chunks = await hybrid_search("新生宿舍怎么申请", topics=["新生入学"], top_k=3)
    assert chunks
    doc = await db["documents"].find_one({"doc_id": chunks[0].doc_id})
    assert doc and doc["url"].startswith(PREFIX)  # 来源引用元数据可达

    if settings.deepseek_api_key:
        from qa_api.generator.llm import stream_answer
        from qa_api.generator.prompts import build_context

        answer = "".join([d async for d in stream_answer("新生宿舍怎么申请？", build_context(chunks))])
        assert answer
    else:
        pytest.skip("DEEPSEEK_API_KEY 未设置，跳过真实 LLM 问答段（检索/来源段已验证）")


async def test_second_run_is_idempotent(monkeypatch):
    """同一采集源跑两遍：Mongo 文档数与 Milvus 行数均不重复（幂等铁律）。"""
    async def run_once():
        monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: make_engine())
        return await tasks_mod.run_collection_task(make_source())

    r1, r2 = await run_once(), await run_once()
    assert r1["status"] == "success" and r2["status"] == "success"

    db = get_mongo()
    docs = [d async for d in db["documents"].find({"url": {"$regex": "^https://demo.it/"}})]
    assert len(docs) == len(DETAILS)
    rows = get_milvus().query(COLLECTION, filter="", output_fields=["id"], limit=1000)
    assert len(rows) == len(DETAILS)  # 每篇 1 个 chunk，两遍后仍 5 行
```

- [ ] **Step 2: 跑测试确认失败（缺 marker 定义时报 warning，测试本体此时跑不了——先验证环境）**

Run: `uv run pytest tests/integration -v`
Expected: ① 若模型服务未起 → FAIL（/embed 连接失败，属于环境前置，先按 Step 0 起服务）；② 环境就绪时 FAIL at 第一个断言（因 `tests/integration/` 目录新建，先确认能 import——本任务无未实现生产代码，测试即「集成验收脚本」，绿色即验收通过）。

- [ ] **Step 3: 无需实现代码——运行即验证（真跑通过即收工）**

Run: `uv run pytest tests/integration -v`
Expected: 2 passed（LLM 段有 key 时真实生成；无 key 时 skip 并明确提示）。若出现真 bug（如过滤表达式报错、Milvus 插入失败），按 systematic-debugging 修复生产代码并补单测，回跑本测试。

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_full_pipeline.py pyproject.toml
git commit -m "test: 全链路集成测试(mock站点5篇真跑存储,含幂等两遍)"
```

---

### Task E2: 降级路径测试（reranker 挂→原序；LLM 主挂→备援；主备全挂→明确报错）

**Files:**
- Create: `tests/test_degradation.py`

**Interfaces:**
- Consumes: `qa_api.reranker.rerank.rerank_chunks(query, chunks)`、`qa_api.retriever.hybrid.ScoredChunk`、`qa_api.generator.llm.stream_answer(query, context, history, llm, backup)`（llm/backup 可注入 stub 客户端）、`shared.errors.ExternalServiceError`、`shared.config.settings`。
- 不依赖任何存储：reranker 用「指向未监听端口」的 `settings.rerank_service_url` 触发真实连接拒绝；LLM 主备用 `openai.AsyncOpenAI(http_client=httpx.AsyncClient(transport=httpx.MockTransport(...)))` 构造 stub（无网络）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_degradation.py
"""降级路径测试（spec §8 降级链契约）：reranker/LLM 主备。"""
import json

import httpx
import pytest
from openai import AsyncOpenAI

from qa_api.generator.llm import stream_answer
from qa_api.reranker.rerank import rerank_chunks
from qa_api.retriever.hybrid import ScoredChunk
from shared.config import settings
from shared.errors import ExternalServiceError


def make_chunks():
    return [ScoredChunk(chunk_id=f"c{i}", doc_id=f"d{i}", text=f"文本{i}",
                        score=s, dense_score=s, sparse_score=0.0)
            for i, s in enumerate([0.9, 0.8, 0.7])]


def test_rerank_down_falls_back_to_original_order(monkeypatch):
    monkeypatch.setattr(settings, "rerank_service_url", "http://127.0.0.1:1/rerank")
    chunks = make_chunks()
    out = rerank_chunks("查询", chunks)
    assert [c.chunk_id for c in out] == [c.chunk_id for c in chunks]  # 原序
    assert [c.score for c in out] == [0.9, 0.8, 0.7]  # 分数未改


def _sse_response(deltas):
    body = "".join(f'data: {json.dumps({"choices": [{"delta": {"content": d}}]}, ensure_ascii=False)}\n\n'
                   for d in deltas) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


def _stub_client(handler):
    return AsyncOpenAI(api_key="stub", base_url="https://stub.invalid/v1",
                       http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_llm_primary_fails_falls_back_to_backup():
    def primary_handler(request):
        return httpx.Response(500, text="primary down")

    def backup_handler(request):
        assert "/chat/completions" in request.url.path
        return _sse_response(["备", "援"])

    parts = [d async for d in stream_answer(
        "测试问题", "知识片段", llm=_stub_client(primary_handler), backup=_stub_client(backup_handler))]
    assert "".join(parts) == "备援"


async def test_llm_both_down_raises_external_error():
    def down(request):
        return httpx.Response(500, text="down")

    with pytest.raises(ExternalServiceError):
        _ = [d async for d in stream_answer(
            "测试问题", "知识片段", llm=_stub_client(down), backup=_stub_client(down))]
```

- [ ] **Step 2: 跑测试确认通过（契约已存在于生产代码，本任务为回归锁定）**

Run: `uv run pytest tests/test_degradation.py -v`
Expected: 3 passed。若 `test_rerank_down...` 因 127.0.0.1:1 被占用（罕见）超时，改为 `http://127.0.0.1:9/rerank`（discard 端口）。

- [ ] **Step 3: Commit**

```bash
git add tests/test_degradation.py
git commit -m "test: 降级路径测试(reranker挂原序兜底/LLM主备切换/主备全挂报错)"
```

---

## 阶段 F：打包交付（主会话直接执行）

### Task F1: 前端容器化 + compose 全栈编排（一条命令起全栈）

**目标**：spec 硬约束 2「空环境一条 `docker compose up` 起全栈」。前端构建产物用 nginx 提供，代理与 vite dev 同构（`/admin-api/`→collector 去前缀、`/qa-api/`→qa-api 去前缀、SSE 关闭缓冲）。

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Modify: `docker-compose.yml`（追加 frontend 服务）
- Modify: `README.md`（快速开始 + 验收状态）

- [ ] **Step 1: 核对本机 pnpm 主版本并锁定镜像内版本**

Run: `pnpm -v`（frontend 目录下）
Expected: 记录主版本（如 9.x / 10.x）。Dockerfile 内 `pnpm@9` 若与本机不一致则改为对应主版本（锁文件向下兼容）。本机锁文件为 pnpm-lock.yaml，容器内用 `--frozen-lockfile` 强制一致。

- [ ] **Step 2: 写 Dockerfile 与 nginx 配置**

`frontend/Dockerfile`：

```dockerfile
# 前端双段构建：node 构建产物 → nginx 静态托管 + 后端反代
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm@9 && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

`frontend/nginx.conf`：

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # 管理端 API → collector（去 /admin-api/ 前缀，与 vite dev rewrite 同构）
    location /admin-api/ {
        proxy_pass http://collector:8002/;
        proxy_set_header Host $host;
        proxy_read_timeout 60s;
    }

    # 问答 SSE → qa-api（关闭缓冲，长连接不断流）
    location /qa-api/ {
        proxy_pass http://qa-api:8003/;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }

    # SPA 路由回退（/admin 直接刷新）
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: compose 追加 frontend 服务**

`docker-compose.yml` services 段末尾（qa-api 之后）追加：

```yaml
  frontend:
    build: ./frontend
    ports: ["5173:80"]
    depends_on: [collector, qa-api]
```

- [ ] **Step 4: README 快速开始更新**

`README.md`「快速开始」段替换为：

```markdown
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
```

- [ ] **Step 5: 构建验证**

Run: `docker compose build frontend && docker compose up -d frontend`
Expected: 镜像构建成功；`curl http://127.0.0.1:5173/` 返回含 `<div id="app">` 的 index.html；`curl http://127.0.0.1:5173/admin` 同样返回 SPA 页（fallback 生效）。

- [ ] **Step 6: Commit**

```bash
git add frontend/Dockerfile frontend/nginx.conf docker-compose.yml README.md
git commit -m "feat: 前端容器化(nginx双端代理+SSE不缓冲),compose一条命令起全栈"
```

---

### Task F2: 空环境复测 + 20 题演示问题清单

**Files:**
- Create: `docs/demo/20-questions.md`

**验收标准（spec §9 硬约束 1）**：20 题答案带来源引用率 100%，无来源不编造。

- [ ] **Step 1: 编写 20 题清单（覆盖六大专题域 + 综合场景）**

`docs/demo/20-questions.md`：

```markdown
# 演示问题清单（20 题，验收素材 + 路演脚本）

> 用途：① 演示视频问答环节素材；② 验收「100% 附来源引用」。每题注明所属专题域与期望来源类型。
> 执行：前端问答端逐题提问，勾选「来源卡片出现 + 答案与来源一致」。

| # | 问题 | 专题域 | 期望来源 |
|---|------|--------|---------|
| 1 | 2026级新生什么时候报到？ | 新生入学 | 模拟·入学报到通知 |
| 2 | 新生怎么办校园卡？ | 新生入学 | 模拟·校园卡指南 |
| 3 | 新生军训是什么时候？ | 新生入学 | 模拟·军训通知 |
| 4 | 港澳台学生入学注册要带什么材料？ | 港澳生服务 | 模拟·注册流程 |
| 5 | 港澳学生住宿怎么安排？ | 港澳生服务 | 模拟·住宿通知 |
| 6 | 港澳台学生的学籍怎么管理？ | 港澳生服务 | 模拟·学籍管理办法 |
| 7 | 怎么申请转专业？ | 教务学籍 | 模拟·转专业指南 |
| 8 | 这学期选课什么时候开始？ | 教务学籍 | 模拟·选课通知 |
| 9 | 本科生最长可以读几年？ | 教务学籍 | 模拟·学籍管理规定 |
| 10 | 想换宿舍怎么申请？ | 后勤生活 | 模拟·调宿流程 |
| 11 | 暑假食堂开放时间？ | 后勤生活 | 模拟·食堂通知 |
| 12 | 校园卡丢了怎么补办？ | 后勤生活 | 模拟·补卡须知 |
| 13 | 秋季招聘会什么时候开？ | 就业创业 | 模拟·招聘会通知 |
| 14 | 大学生创业项目怎么申报？ | 就业创业 | 模拟·创业申报指南 |
| 15 | 学校有简历指导讲座吗？ | 就业创业 | 模拟·讲座新闻 |
| 16 | 校级科研项目怎么申报？ | 科研学术 | 模拟·科研申报通知 |
| 17 | 学校最近有什么科研成果？ | 科研学术 | 模拟·论文新闻 |
| 18 | 进实验室要先办什么手续？ | 科研学术 | 模拟·安全准入指南 |
| 19 | 学校最近发布了什么通知？ | 综合 | 真实·gzhu 通知公告（真实采集能力证明） |
| 20 | 广州大学新闻网上有什么动态？ | 综合 | 真实·gznews 新闻（真实采集能力证明） |

**验收记录**：逐题提问后勾选并统计来源引用率（目标 100%）。诚实降级：题库未覆盖的问题应回答「未找到」并给建议方向（路演时可演示 1 题「问一个知识库没有的问题」展示不编造）。
```

- [ ] **Step 2: 空环境复测 runbook（主会话真执行，结果记入 PROGRESS）**

```powershell
# 1. 全栈起（含前端）
docker compose up -d --build
# 2. MinIO 桶（seed 脚本已自动确保）→ 直接播种
uv run python -m scripts.seed_demo
# 3. 后端全量测试（集成测试真跑存储）
uv run pytest tests/ -v
# 4. 前端构建测试
cd frontend; pnpm build; pnpm vitest run; cd ..
# 5. 20 题清单逐题过（浏览器 http://localhost:5173）——记录来源引用率
```

Expected: 全量测试全绿（35+ 单测 + 集成 2 + 新增约 15 ≈ 52+）；20 题来源引用率 100%。

- [ ] **Step 3: Commit**

```bash
git add docs/demo/20-questions.md
git commit -m "docs: 20题演示问题清单(六大专题域+综合,验收素材与路演脚本)"
```

---

### Task F3: 作品说明书 + 演示视频脚本 + 进度收尾

**Files:**
- Create: `docs/作品说明书.md`
- Create: `docs/演示视频脚本.md`
- Modify: `docs/PROGRESS.md`（进度同步：Plan 3 完成）
- Modify: `README.md`（文档索引补两篇）

- [ ] **Step 1: 作品说明书（大赛交付文档）**

`docs/作品说明书.md` 按以下结构成文（每节内容落点已给定）：

```markdown
# 作品说明书：面向校务管理的 AI 自动数据采集与知识管理中台

## 一、作品简介
一句话定位（spec §1）+ 立项三问结论（给谁用/硬约束/砍掉什么）。

## 二、创新点
主创新 1 多源异构自动采集管道（增量去重/LLM 兜底解析/站点适配器/任务状态机）；
主创新 2 可信问答（100% 来源引用、时间衰减、过期降权标注、无来源不编造）；
辅助 3 湾区特色专题知识域（六大专题域）；
辅助 4 知识全生命周期管理（采集→打标→时效→入库→到期检测→资产全景）。

## 三、系统架构
架构图（spec §4 ASCII 图复用）+ 三服务职责边界 + 数据流四条主线（spec §5）。

## 四、关键技术
- 检索链路：BGE-M3 dense+sparse 双路 → min-max 归一化融合(0.8/0.2) → 时间衰减(半衰期 30 天) → 过期降权(×0.25) → bge-reranker-large 精排 → 断崖截断(0.3)（ADR-006 参数）
- 采集管道：httpx+selectolax → trafilatura+LLM 兜底 → 规则+LLM 双级打标 → 幂等三写入库（先删后插）
- 降级链：DeepSeek→DashScope；reranker→原序；sparse→仅 dense；MinIO→快照缺失标记（spec §8）

## 五、运行与部署
一条 docker compose up 起全栈（README 快速开始）+ 模型权重本地挂载 + .env 配置说明。

## 六、演示数据与验收
真实采集（gzhu 8 篇）+ 模拟数据（六大专题域 18 篇，脚本可复现）；20 题清单来源引用率 100%；后端测试通过数（以实际为准）。

## 七、技术选型决策（ADR 摘要）
11 条 ADR 一句话摘要表（编号/决策/一句话理由）。
```

- [ ] **Step 2: 演示视频脚本（约 5 分钟分镜）**

`docs/演示视频脚本.md`：

```markdown
# 演示视频脚本（约 5 分钟）

> 每镜注明时间/画面/旁白要点；录制环境：全栈 compose 起、18 篇模拟 + 真实采集数据在库。

| # | 时间 | 画面 | 旁白要点 |
|---|------|------|---------|
| 1 | 0:00-0:20 | 标题页 + 选题背景 | 校务信息分散难查 → 中台定位一句话 |
| 2 | 0:20-0:50 | 管理端采集源页：已有 gzhu/gznews 源 + 点击「立即采集」 | AI 自动采集：任务状态实时流转（待运行→运行中→成功） |
| 3 | 0:50-1:20 | 知识库页：真实采集 8 篇（gzhu 官网通知）+ 播种 18 篇模拟数据，六大专题域筛选 | 真实采集证明能力，模拟数据覆盖演示场景，知识全生命周期（分类/专题/时效/上下架） |
| 4 | 1:20-1:50 | 资产全景页：指标卡 + 分类/专题图表 | 知识资产管理：资产全景、到期检测 |
| 5 | 1:50-3:20 | 问答端逐题演示（20 题清单挑 4-5 题：新生报到/转专业/招聘会/综合通知） | SSE 流式回答 + 每条答案附来源卡片（标题/栏目/日期/链接），专题域筛选 |
| 6 | 3:20-3:50 | 可信性演示：① 点开来源卡片跳转原文；② 问一个知识库没有的问题 → 诚实回答「未找到」+ 建议方向 | 答案可信：100% 来源引用，无来源不编造 |
| 7 | 3:50-4:20 | 架构图 + 一条 docker compose up 起全栈回放 | 三服务分层 + 单机稳定复现 |
| 8 | 4:20-5:00 | 结尾：创新点总结 + 演示数据来源声明 | 真实+模拟数据声明（诚实原则） |
```

- [ ] **Step 3: PROGRESS 收尾同步**

`docs/PROGRESS.md`：①「已完成」表追加 Plan 3 各任务 commit；②「当前进度」更新为全部完成；③「待执行」清空并改为可选后续（如 RAGAS 评测/移动端等 spec §11 范围外事项）；④ 冒烟验证记录追加 Plan 3 验收结论（20 题引用率、全量测试数、一条 compose 起全栈）。

`README.md` 文档索引表追加两行：`docs/作品说明书.md`、`docs/演示视频脚本.md`。

- [ ] **Step 4: 全量最终核验**

Run: `uv run pytest tests/ -v`；`docker compose config`（语法）；`git status` 无遗漏。
Expected: 全绿 + 工作区干净。

- [ ] **Step 5: Commit**

```bash
git add docs/作品说明书.md docs/演示视频脚本.md docs/PROGRESS.md README.md
git commit -m "docs: 作品说明书+演示视频脚本,PROGRESS同步Plan3完成"
```

---

## 执行顺序与派活（ADR-011）

| 阶段 | 任务 | 执行方 | 依赖 |
|------|------|--------|------|
| D | D1、D2、D3 | workflow 批量派 `glm-5.3`（一批 3 任务） | D3 依赖 D2（rule_tag_topics） |
| E | E1、E2 | workflow 批量派 `glm-5.3`（代码编写）；**E1 真跑验证由主会话执行** | E1 依赖 D2；前置存储 + model_server:8001 |
| F | F1、F2、F3 | 主会话 deepseek-v4-pro 直接执行 | 依赖 D/E 完成 |

**验收铁律（AGENTS.md/ADR-011）**：每个派发批次完成后，主会话逐任务核验磁盘状态（文件存在、测试绿、commit 存在），不以 workflow 返回值/子代理报告为验收依据；子代理失败主会话直接接管补做，不反复重派空转。

**冒烟环境注意（PROGRESS.md 已记录）**：DSH 起服务/跑集成需先注入用户级 `DEEPSEEK_API_KEY`；Windows localhost 可能解析 IPv6，测试用 `127.0.0.1`。

