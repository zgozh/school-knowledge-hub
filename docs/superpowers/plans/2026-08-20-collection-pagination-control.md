# 采集页数控制器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给采集源加「采集页数」档位（1/3/5/10/全部，全部内部封顶 50 页），默认 1 页；翻页能力抽象为适配器通用接口 `next_page_url`，引擎/档位/去重/入库全站点通用。

**Architecture:** `SiteAdapter` 基类加 `next_page_url`（默认 None=不翻页）→ 新增 `collector/crawler/gzhu_cms.py` 的 `GUZhuCMSAdapter` 实现「解析 a.Next 下页链接 + urljoin 拼绝对地址」→ gzhu/gznews 适配器继承它（保留各自 `_abs_url`/栏目/选择器差异）。引擎 `fetch_source` 加 `max_pages` 翻页循环（`_seen` 去重跨页生效，`MAX_PAGES_CAP=50`）；`SourceConfig` 加 `max_pages: int = 1`；前端 SourcesView 加「采集页数」下拉。

**Tech Stack:** FastAPI + selectolax + httpx + pytest（后端）/ Vue3 + Element Plus + vitest（前端）。

**Spec:** `docs/superpowers/specs/2026-08-20-collection-pagination-control-design.md`

## Global Constraints

- 翻页逻辑只写在 `gzhu_cms.py` 适配器层，**不把站点选择器写进通用基类 `SiteAdapter` 或引擎**（基类 `next_page_url` 只返回 `None`）。
- `SourceConfig.max_pages: int = 1`；档位 `1/3/5/10/0`，`0`=「全部」；`from_dict` 用 `d.get("max_pages", 1)`（存量源向后兼容）。
- 引擎 `MAX_PAGES_CAP = 50`；`effective_max = max_pages if max_pages > 0 else MAX_PAGES_CAP`。
- `fetch_source` 返回三元素元组 `(articles, failures, page_capped)`；`page_capped` 仅当「全部」档打到 `MAX_PAGES_CAP` 且仍有下页时为 `True`。
- TDD：先写失败测试 → 看失败 → 最小实现 → 看通过 → commit（每任务一个 commit）。
- 后端测试命令：`uv run pytest tests/<file>.py -v`（本计划各任务均为纯 mock，无需 `DEEPSEEK_API_KEY`）。
- 前端测试命令：在 `frontend/` 目录跑 `pnpm exec vitest run tests/<file>.test.js`。

---

### Task 1: 适配器 `next_page_url` 接口 + `GUZhuCMSAdapter` 共享层

**Files:**
- Modify: `collector/crawler/base.py`（`SiteAdapter` 加 `next_page_url` 默认返回 None）
- Create: `collector/crawler/gzhu_cms.py`（`GUZhuCMSAdapter`）
- Modify: `collector/crawler/gzhu.py`（`GUZhuAdapter` 改继承 `GUZhuCMSAdapter`，保留 `_abs_url`/选择器）
- Modify: `collector/crawler/gznews.py`（`GUNewsAdapter` 改继承 `GUZhuCMSAdapter`，保留选择器）
- Test: `tests/test_pagination.py`（新建）

**Interfaces:**
- Produces: `SiteAdapter.next_page_url(self, html: str, base_url: str) -> str | None`（基类默认返回 `None`）；`GUZhuCMSAdapter.next_page_url` 解析 `a.Next` 的 `href` 并用 `urllib.parse.urljoin(base_url, href)` 拼绝对地址，无 `a.Next`（末页是 `span.NextDisabled`）返回 `None`。

- [ ] **Step 1: 写失败测试** `tests/test_pagination.py`

```python
# tests/test_pagination.py
"""翻页接口测试：基类默认不翻页 + gzhu_cms 解析下页链接。"""
from collector.crawler.base import SiteAdapter
from collector.crawler.gzhu import GUZhuAdapter
from collector.crawler.gzhu_cms import GUZhuCMSAdapter
from collector.crawler.gznews import GUNewsAdapter

NEXT_HTML = """
<html><body><ul><li><a href="info/1087/33327.htm">文章</a></li></ul>
<div class="pages"><a href="tzgg/2.htm" class="Next">下页</a></div></body></html>
"""

LAST_HTML = """
<html><body><ul><li><a href="info/1087/33327.htm">文章</a></li></ul>
<div class="pages"><span class="NextDisabled">下页</span></div></body></html>
"""


def test_base_adapter_next_page_url_returns_none():
    assert SiteAdapter().next_page_url(NEXT_HTML, "https://www.gzhu.edu.cn/z__l/tzgg.htm") is None


def test_gzhu_cms_next_page_url_returns_absolute_url():
    adapter = GUZhuCMSAdapter()
    got = adapter.next_page_url(NEXT_HTML, "https://www.gzhu.edu.cn/z__l/tzgg.htm")
    # urljoin(base, "tzgg/2.htm") → 相对列表页目录拼接（不能用 _abs_url 的域名根拼接）
    assert got == "https://www.gzhu.edu.cn/z__l/tzgg/2.htm"


def test_gzhu_cms_last_page_returns_none():
    adapter = GUZhuCMSAdapter()
    assert adapter.next_page_url(LAST_HTML, "https://www.gzhu.edu.cn/z__l/tzgg.htm") is None


def test_gzhu_and_gznews_inherit_next_page_url():
    # 继承共享层：gzhu/gznews 适配器获得翻页能力，且各自 _abs_url/选择器不受影响
    assert GUZhuAdapter().next_page_url(NEXT_HTML, "https://www.gzhu.edu.cn/z__l/tzgg.htm") \
        == "https://www.gzhu.edu.cn/z__l/tzgg/2.htm"
    assert GUNewsAdapter().next_page_url(NEXT_HTML, "https://news.gzhu.edu.cn/ttgd.htm") \
        == "https://news.gzhu.edu.cn/ttgd/2.htm"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_pagination.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'collector.crawler.gzhu_cms'`

- [ ] **Step 3: 写最小实现**

`collector/crawler/base.py` 在 `SiteAdapter` 加方法（放在 `_text` 之后）：

```python
    def next_page_url(self, html: str, base_url: str) -> str | None:
        """列表页下一页绝对 URL；默认 None = 不翻页（站点翻页能力由子适配器实现）。"""
        return None
```

`collector/crawler/gzhu_cms.py`（新建）：

```python
"""gzhu CMS 共享层：列表页底部分页「下页」链接解析（gzhu/gznews 共用）。"""
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from collector.crawler.base import SiteAdapter


class GUZhuCMSAdapter(SiteAdapter):
    """gzhu 系 CMS 适配器共享基类：实现翻页；站点差异（_abs_url/栏目/选择器）由子类保留。"""

    def next_page_url(self, html: str, base_url: str) -> str | None:
        # 下页形如 <a href="tzgg/8.htm" class="Next">下页</a>；末页为 <span class="NextDisabled">下页</span>
        tree = HTMLParser(html)
        a = tree.css_first("a.Next")
        if a is None:
            return None
        href = a.attributes.get("href")
        if not href:
            return None
        # 分页 href 是相对路径，须 urljoin（不能用 gzhu._abs_url 的域名根拼接——那是为 /info/ 文章链接设计的）
        return urljoin(base_url, href)
```

`collector/crawler/gzhu.py` 改继承与 import：

```python
from collector.crawler.base import ArticleRef, RawArticle
from collector.crawler.gzhu_cms import GUZhuCMSAdapter


class GUZhuAdapter(GUZhuCMSAdapter):
    site = "gzhu"
    # parse_list/parse_detail/_abs_url 保持不变（本任务仅改继承关系）
```

（原 `from collector.crawler.base import ArticleRef, RawArticle, SiteAdapter` 去掉 `SiteAdapter`；`class GUZhuAdapter(SiteAdapter)` 改为 `class GUZhuAdapter(GUZhuCMSAdapter)`，其余不动。）

`collector/crawler/gznews.py` 同理：

```python
from collector.crawler.base import ArticleRef, RawArticle
from collector.crawler.gzhu_cms import GUZhuCMSAdapter


class GUNewsAdapter(GUZhuCMSAdapter):
    site = "gznews"
    # parse_list/parse_detail 保持不变
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_pagination.py tests/test_adapters.py -v`
Expected: PASS（新增 4 + 原 4 = 8 passed，验证继承不破坏原解析行为）

- [ ] **Step 5: Commit**

```bash
git add collector/crawler/base.py collector/crawler/gzhu_cms.py collector/crawler/gzhu.py collector/crawler/gznews.py tests/test_pagination.py
git commit -m "feat: 适配器next_page_url接口+gzhu_cms共享层(gzhu/gznews继承)"
```

---

### Task 2: `SourceConfig.max_pages` + `from_dict` 向后兼容 + `create_source` 透传

**Files:**
- Modify: `collector/sources.py`
- Modify: `collector/api/sources.py`
- Test: `tests/test_sources.py`（新建）

**Interfaces:**
- Consumes: 无。
- Produces: `SourceConfig.max_pages: int = 1`（dataclass 字段）；`SourceConfig.from_dict` 读 `d.get("max_pages", 1)`；`create_source(payload)` 传 `max_pages=payload.get("max_pages", 1)`。

- [ ] **Step 1: 写失败测试** `tests/test_sources.py`

```python
# tests/test_sources.py
"""SourceConfig.max_pages 字段 + create_source 透传测试。"""
import httpx
import pytest

from collector.api import sources as sources_api
from collector.main import app
from collector.sources import SourceConfig


def test_from_dict_defaults_max_pages_to_1():
    cfg = SourceConfig.from_dict({"id": "s1", "name": "主站公告", "list_url": "https://x/list.htm",
                                  "adapter": "gzhu"})
    assert cfg.max_pages == 1


def test_from_dict_reads_explicit_max_pages():
    cfg = SourceConfig.from_dict({"id": "s1", "name": "主站公告", "list_url": "https://x/list.htm",
                                  "adapter": "gzhu", "max_pages": 3})
    assert cfg.max_pages == 3


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_source_passes_max_pages(client, monkeypatch):
    captured = []
    async def fake_save(cfg):
        captured.append(cfg)
        return "s1"
    monkeypatch.setattr(sources_api.sources, "save_source", fake_save)
    resp = await client.post("/api/admin/sources", json={
        "name": "主站公告", "list_url": "https://x/list.htm", "adapter": "gzhu", "max_pages": 5,
    })
    assert resp.status_code == 200
    assert captured[0].max_pages == 5


async def test_create_source_defaults_max_pages_to_1(client, monkeypatch):
    captured = []
    async def fake_save(cfg):
        captured.append(cfg)
        return "s1"
    monkeypatch.setattr(sources_api.sources, "save_source", fake_save)
    resp = await client.post("/api/admin/sources", json={
        "name": "主站公告", "list_url": "https://x/list.htm", "adapter": "gzhu",
    })
    assert resp.status_code == 200
    assert captured[0].max_pages == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_sources.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'max_pages'`（`from_dict` 未读 max_pages；`create_source` 未传 max_pages）

- [ ] **Step 3: 写最小实现**

`collector/sources.py` 的 `SourceConfig` 加字段 + `from_dict` 读字段：

```python
@dataclass
class SourceConfig:
    id: str
    name: str
    list_url: str
    adapter: str
    enabled: bool = True
    interval_minutes: int = 360
    max_pages: int = 1   # 1/3/5/10/0；0 = 「全部」（内部封顶 50 页）

    @staticmethod
    def from_dict(d: dict) -> "SourceConfig":
        return SourceConfig(id=d["id"], name=d["name"], list_url=d["list_url"],
                            adapter=d["adapter"], enabled=d.get("enabled", True),
                            interval_minutes=d.get("interval_minutes", 360),
                            max_pages=d.get("max_pages", 1))
```

`collector/api/sources.py` 的 `create_source` 加 `max_pages`：

```python
@router.post("")
async def create_source(payload: dict):
    cfg = SourceConfig(id="", name=payload["name"], list_url=payload["list_url"],
                       adapter=payload["adapter"], enabled=payload.get("enabled", True),
                       interval_minutes=payload.get("interval_minutes", 360),
                       max_pages=payload.get("max_pages", 1))
    return {"id": await sources.save_source(cfg)}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_sources.py tests/test_admin_api.py -v`
Expected: PASS（新增 4 + 原 admin_api 用例，全部绿）

- [ ] **Step 5: Commit**

```bash
git add collector/sources.py collector/api/sources.py tests/test_sources.py
git commit -m "feat: SourceConfig加max_pages(默认1向后兼容)+create_source透传"
```

---

### Task 3: 引擎 `fetch_source` 翻页循环 + `MAX_PAGES_CAP` + `page_capped`

**Files:**
- Modify: `collector/crawler/engine.py`（`fetch_source` 加 `max_pages` 参数与翻页循环；返回三元素元组）
- Modify: `tests/test_engine.py`（既有两用例解包三元素）
- Test: `tests/test_engine_pagination.py`（新建）

**Interfaces:**
- Consumes: `adapter.next_page_url(html, base_url)`（Task 1）、`adapter.parse_list/parse_detail`、`url_hash/content_hash`。
- Produces: `CrawlEngine.fetch_source(list_url, adapter, max_pages=1) -> tuple[list[RawArticle], list[dict], bool]`；模块常量 `MAX_PAGES_CAP = 50`。

- [ ] **Step 1: 写失败测试** `tests/test_engine_pagination.py`

```python
# tests/test_engine_pagination.py
"""引擎多页翻页测试：max_pages 档位、跨页去重、MAX_PAGES_CAP 封顶。"""
from collector.crawler import engine as engine_mod
from collector.crawler.base import ArticleRef, RawArticle, SiteAdapter
from collector.crawler.engine import CrawlEngine


class PagedAdapter(SiteAdapter):
    """测试适配器：解析 a.info 条目 + a.Next 下页链接。"""
    site = "paged"

    def parse_list(self, html, base_url):
        from selectolax.parser import HTMLParser
        return [ArticleRef(url=a.attributes["href"], title=a.text(strip=True))
                for a in HTMLParser(html).css("a.info")]

    def next_page_url(self, html, base_url):
        from selectolax.parser import HTMLParser
        a = HTMLParser(html).css_first("a.Next")
        return a.attributes["href"] if a else None

    def parse_detail(self, html, ref):
        return RawArticle(url=ref.url, title=ref.title, html=html, publish_date=None,
                          source_site="paged", column="测试")


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        pass


class FakeHTTP:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    async def get(self, url, **kwargs):
        self.requests.append(url)
        if url in self.pages:
            return FakeResponse(self.pages[url])
        return FakeResponse("<html>detail</html>")


def page_html(urls, next_url):
    links = "".join(f'<a class="info" href="{u}">t</a>' for u in urls)
    nav = f'<a class="Next" href="{next_url}">下页</a>' if next_url else '<span class="NextDisabled">下页</span>'
    return f"<html><body>{links}{nav}</body></html>"


async def test_max_pages_2_fetches_two_pages_and_dedups_across_pages():
    pages = {
        "https://x/list.htm": page_html(["https://x/info/1.htm", "https://x/info/2.htm"], "https://x/list2.htm"),
        "https://x/list2.htm": page_html(["https://x/info/2.htm", "https://x/info/3.htm"], None),  # 2 跨页重复
    }
    engine = CrawlEngine(http_client=FakeHTTP(pages))
    articles, failures, capped = await engine.fetch_source("https://x/list.htm", PagedAdapter(), max_pages=2)
    assert {a.url for a in articles} == {"https://x/info/1.htm", "https://x/info/2.htm", "https://x/info/3.htm"}
    assert failures == [] and capped is False


async def test_max_pages_1_fetches_only_first_page():
    pages = {
        "https://x/list.htm": page_html(["https://x/info/1.htm"], "https://x/list2.htm"),
        "https://x/list2.htm": page_html(["https://x/info/2.htm"], None),
    }
    http = FakeHTTP(pages)
    engine = CrawlEngine(http_client=http)
    articles, _, _ = await engine.fetch_source("https://x/list.htm", PagedAdapter(), max_pages=1)
    assert {a.url for a in articles} == {"https://x/info/1.htm"}
    assert "https://x/list2.htm" not in http.requests


async def test_max_pages_0_goes_to_last_page():
    pages = {
        "https://x/list.htm": page_html(["https://x/info/1.htm"], "https://x/list2.htm"),
        "https://x/list2.htm": page_html(["https://x/info/2.htm"], None),
    }
    engine = CrawlEngine(http_client=FakeHTTP(pages))
    articles, _, capped = await engine.fetch_source("https://x/list.htm", PagedAdapter(), max_pages=0)
    assert {a.url for a in articles} == {"https://x/info/1.htm", "https://x/info/2.htm"}
    assert capped is False


async def test_max_pages_0_caps_at_MAX_PAGES_CAP(monkeypatch):
    monkeypatch.setattr(engine_mod, "MAX_PAGES_CAP", 3)
    pages = {}
    for i in range(1, 6):
        url = "https://x/list.htm" if i == 1 else f"https://x/list{i}.htm"
        nxt = f"https://x/list{i + 1}.htm" if i < 5 else None
        pages[url] = page_html([f"https://x/info/{i}.htm"], nxt)
    engine = CrawlEngine(http_client=FakeHTTP(pages))
    articles, _, capped = await engine.fetch_source("https://x/list.htm", PagedAdapter(), max_pages=0)
    assert len(articles) == 3  # 打到封顶 3 页即停
    assert capped is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_engine_pagination.py -v`
Expected: FAIL — `TypeError: fetch_source() got an unexpected keyword argument 'max_pages'`

- [ ] **Step 3: 写最小实现** `collector/crawler/engine.py`

在类外定义常量，重写 `fetch_source`（把逐详情抓取内联为 `fetch_one` 闭包，翻页循环调用）：

```python
MAX_PAGES_CAP = 50


class CrawlEngine:
    DEFAULT_HEADERS = { ... }  # 不变

    def __init__(self, http_client=None):
        self._http = http_client or httpx.AsyncClient(...)  # 不变
        self._seen: set[str] = set()

    def has_seen(self, key): ...  # 不变
    def set_seen(self, key): ...  # 不变

    async def fetch_source(self, list_url, adapter, max_pages=1):
        """抓取列表页并翻页：返回 (新文章列表, 失败清单, page_capped)。"""
        effective_max = max_pages if max_pages > 0 else MAX_PAGES_CAP
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
                try:
                    articles.append(adapter.parse_detail(resp.text, ref))
                except Exception as e:
                    failures.append({"url": ref.url, "error": str(e)})

        page = 0
        current_url = list_url
        page_capped = False
        while True:
            try:
                resp = await self._http.get(current_url)
                resp.raise_for_status()
            except Exception as e:
                raise ExternalServiceError(f"列表页抓取失败 {current_url}: {e}") from e
            refs = adapter.parse_list(resp.text, current_url)
            await asyncio.gather(*(fetch_one(r) for r in refs))
            page += 1
            next_url = adapter.next_page_url(resp.text, current_url)
            if page >= effective_max:
                # 「全部」档（effective_max == 封顶）且仍有下页 → 标记封顶
                if next_url is not None and effective_max == MAX_PAGES_CAP:
                    page_capped = True
                break
            if next_url is None:
                break
            current_url = next_url
        return articles, failures, page_capped

    async def close(self): ...  # 不变
```

同时改 `tests/test_engine.py` 既有两用例的解包（三元素）：

```python
    articles, failures, _ = await engine.fetch_source("https://x/list.htm", adapter)
    ...
    articles2, _, _ = await engine.fetch_source("https://x/list.htm", adapter)
    ...
    articles, failures, _ = await engine.fetch_source("https://x/list.htm", adapter)
```

（既有 `FakeAdapter` 未实现 `next_page_url` → 走基类默认 None，仍单页，行为不变。）

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_engine.py tests/test_engine_pagination.py -v`
Expected: PASS（原 2 + 新增 4 = 6 passed）

- [ ] **Step 5: Commit**

```bash
git add collector/crawler/engine.py tests/test_engine.py tests/test_engine_pagination.py
git commit -m "feat: 引擎fetch_source翻页循环(MAX_PAGES_CAP=50+page_capped)"
```

---

### Task 4: `tasks.py` 透传 `max_pages` + 记录 `page_capped`

**Files:**
- Modify: `collector/tasks.py`
- Modify: `tests/test_tasks.py`、`tests/test_topic_rules.py`（fetch_source mock 改三元素）

**Interfaces:**
- Consumes: `fetch_source(list_url, adapter, max_pages) -> (articles, failures, page_capped)`（Task 3）、`source.max_pages`（Task 2）。
- Produces: `run_collection_task(source)` 结果 dict 新增 `"page_capped": bool`；`task_runs` 更新 `$set` 加 `page_capped`。

- [ ] **Step 1: 写失败测试**（改 `tests/test_tasks.py`）

```python
from unittest.mock import AsyncMock

from collector import tasks as tasks_mod


def _fake_mongo():
    fake = AsyncMock()
    fake.insert_one = AsyncMock()
    fake.update_one = AsyncMock()
    fake.__getitem__.return_value = fake
    return fake


async def test_run_task_partial_failure(monkeypatch):
    """单页失败→部分失败状态；结果记录成功/失败数。"""
    fake_engine = AsyncMock()
    fake_engine.fetch_source = AsyncMock(return_value=([], [{"url": "https://x/1.htm", "error": "超时"}], False))
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: fake_engine)
    monkeypatch.setattr(tasks_mod, "get_mongo", lambda: _fake_mongo())
    source = tasks_mod.SourceConfig(id="s1", name="主站公告", list_url="https://www.gzhu.edu.cn/z__l/tzgg.htm",
                                    adapter="gzhu", enabled=True, interval_minutes=60)
    result = await tasks_mod.run_collection_task(source)
    assert result["status"] == "partial"
    assert result["failed"] == 1
    assert result["succeeded"] == 0
    assert result["page_capped"] is False


async def test_run_task_passes_max_pages_and_records_capped(monkeypatch):
    """fetch_source 收到 source.max_pages；page_capped 记入返回结果与 task_runs。"""
    fake_engine = AsyncMock()
    fake_engine.fetch_source = AsyncMock(return_value=([], [], True))
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: fake_engine)
    fake_mongo = _fake_mongo()
    monkeypatch.setattr(tasks_mod, "get_mongo", lambda: fake_mongo)
    source = tasks_mod.SourceConfig(id="s1", name="x", list_url="https://x/list.htm",
                                    adapter="gzhu", enabled=True, interval_minutes=60, max_pages=3)
    result = await tasks_mod.run_collection_task(source)
    # 透传 max_pages 到 fetch_source（第 3 个位置参数）
    assert fake_engine.fetch_source.await_args.args[2] == 3
    assert result["page_capped"] is True
    # task_runs 更新带 page_capped
    update_call = fake_mongo.update_one.await_args
    assert update_call.args[1]["$set"]["page_capped"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_tasks.py -v`
Expected: FAIL — `test_run_task_passes_max_pages_and_records_capped` 断言失败（fetch_source 未收 max_pages / 结果无 page_capped）

- [ ] **Step 3: 写最小实现** `collector/tasks.py`

```python
@async_retry(retries=3, base_delay=2.0, max_delay=30.0)
async def _fetch_with_retry(engine: CrawlEngine, source: SourceConfig):
    return await engine.fetch_source(source.list_url, _load_adapter(source.adapter), source.max_pages)
```

`run_collection_task` 中改解包 + 结果/落库带 page_capped：

```python
    engine = CrawlEngine()
    try:
        raw_articles, failures, page_capped = await _fetch_with_retry(engine, source)
    except ExternalServiceError as e:
        ...  # failed 分支不变
```

末尾更新：

```python
    status = "success" if not failures else "partial"
    await db["task_runs"].update_one({"task_id": task_id},
                                     {"$set": {"status": status, "succeeded": succeeded,
                                               "failed": len(failures), "failures": failures,
                                               "page_capped": page_capped,
                                               "finished_at": datetime.now().isoformat()}})
    logger.info("任务结束 %s status=%s 成功=%d 失败=%d", task_id, status, succeeded, len(failures))
    return {"task_id": task_id, "status": status, "succeeded": succeeded, "failed": len(failures),
            "page_capped": page_capped}
```

同时改 `tests/test_topic_rules.py` 的 fetch_source mock 返回三元素：

```python
    fake_engine.fetch_source = AsyncMock(return_value=(
        [RawArticle(url="https://x/1.htm", title="关于新生入学宿舍申请的通知", html="<html>x</html>",
                    publish_date="2026-08-10", source_site="gzhu", column="通知公告")], [], False))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_tasks.py tests/test_topic_rules.py -v`
Expected: PASS（test_tasks 2 + topic_rules 3 = 5 passed）

- [ ] **Step 5: Commit**

```bash
git add collector/tasks.py tests/test_tasks.py tests/test_topic_rules.py
git commit -m "feat: 任务编排透传max_pages+记录page_capped"
```

---

### Task 5: 前端 SourcesView「采集页数」下拉

**Files:**
- Modify: `frontend/src/views/admin/SourcesView.vue`
- Test: `frontend/tests/sourcesView.test.js`（新建）

**Interfaces:**
- Consumes: 无新增（`useSources().create(payload)` 原样透传；`adminApi.createSource` 已按 payload 原样 POST，无需改 `admin.js`）。
- Produces: 表单 `form.max_pages`（默认 `1`）+「采集页数」下拉（5 档：`1 页（默认）/3 页/5 页/10 页/全部`，值 `1/3/5/10/0`）。

- [ ] **Step 1: 写失败测试** `frontend/tests/sourcesView.test.js`

```js
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const mocks = vi.hoisted(() => ({
  listSources: vi.fn(),
  createSource: vi.fn(),
  deleteSource: vi.fn(),
  runTask: vi.fn(),
}))

vi.mock('../src/api/admin', () => ({ adminApi: mocks }))

import SourcesView from '../src/views/admin/SourcesView.vue'

function mountView() {
  return mount(SourcesView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

function setNativeInput(el, value) {
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
}

async function openCreate(wrapper) {
  const btn = Array.from(wrapper.findAll('button')).find((b) => b.text().includes('新增采集源'))
  await btn.trigger('click')
  await flushPromises()
}

/** 点开某 label 的表单项里的 el-select 下拉，返回下拉里所有 option 的文本。 */
async function openSelectOptions(label) {
  const formItem = Array.from(document.body.querySelectorAll('.el-form-item')).find((item) =>
    item.querySelector('.el-form-item__label')?.textContent.includes(label))
  const select = formItem.querySelector('.el-select')
  select.querySelector('.el-select__wrapper').dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()
  return Array.from(document.body.querySelectorAll('.el-select-dropdown__item')).map((o) => o.textContent.trim())
}

async function pickOption(label, text) {
  const opts = await openSelectOptions(label)
  const target = Array.from(document.body.querySelectorAll('.el-select-dropdown__item'))
    .find((o) => o.textContent.includes(text))
  target.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()
}

describe('SourcesView 采集页数控制器', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listSources.mockResolvedValue({ items: [] })
    mocks.createSource.mockResolvedValue({ id: 's1' })
  })
  afterEach(() => { document.body.innerHTML = '' })

  it('新增弹窗渲染「采集页数」下拉 5 档，默认 1 页', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openCreate(wrapper)
    expect(document.body.textContent).toContain('采集页数')
    const opts = await openSelectOptions('采集页数')
    expect(opts).toEqual(['1 页（默认）', '3 页', '5 页', '10 页', '全部'])
    expect(document.body.textContent).toContain('1 页（默认）')
  })

  it('选择 3 页后提交，createSource payload 含 max_pages=3', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openCreate(wrapper)
    setNativeInput(document.body.querySelector('input[placeholder="如：广州大学教务处"]'), '测试源')
    setNativeInput(document.body.querySelector('input[placeholder="https://..."]'), 'https://www.gzhu.edu.cn/z__l/tzgg.htm')
    await pickOption('适配器', '广州大学主站')
    await pickOption('采集页数', '3 页')
    const saveBtn = Array.from(document.body.querySelectorAll('button')).find((b) => b.textContent.includes('确定'))
    saveBtn.click()
    await flushPromises()
    expect(mocks.createSource).toHaveBeenCalled()
    expect(mocks.createSource.mock.calls[0][0].max_pages).toBe(3)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run（`frontend/` 目录）: `pnpm exec vitest run tests/sourcesView.test.js`
Expected: FAIL — 弹窗无「采集页数」文本（`toContain('采集页数')` 失败）

- [ ] **Step 3: 写最小实现** `frontend/src/views/admin/SourcesView.vue`

模板在「采集间隔」表单项之后加：

```vue
        <el-form-item label="采集页数" prop="max_pages">
          <el-select v-model="form.max_pages" style="width: 100%">
            <el-option v-for="opt in PAGE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
```

`<script setup>` 加常量与默认值：

```js
const PAGE_OPTIONS = [
  { label: '1 页（默认）', value: 1 },
  { label: '3 页', value: 3 },
  { label: '5 页', value: 5 },
  { label: '10 页', value: 10 },
  { label: '全部', value: 0 },
]
const defaultForm = { name: '', list_url: '', adapter: '', enabled: true, interval_minutes: 360, max_pages: 1 }
```

（`onCreate` 的 `create({ ...form })` 已把 `max_pages` 一并透传给 `adminApi.createSource`，无需改 `admin.js`。）

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm exec vitest run tests/sourcesView.test.js`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/admin/SourcesView.vue frontend/tests/sourcesView.test.js
git commit -m "feat: 采集源表单加采集页数下拉(1/3/5/10/全部)"
```

---

### Task 6: 文档同步 + 全量回归 + 容器真跑

**Files:**
- Modify: `README.md`（功能清单 + 测试数字）
- Modify: `docs/PROGRESS.md`（「采集页数控制器」段从「待实现」改为「已完成」，记 commit 与验收证据）

- [ ] **Step 1: 全量回归后端**

Run: `uv run pytest tests/ -q`
Expected: 全绿（原 87 + 新增 4 + 4 + 4 + 1 ≈ **100 passed**，含 integration 时须存储在线）

- [ ] **Step 2: 全量回归前端**

Run（`frontend/` 目录）: `pnpm exec vitest run` 然后 `pnpm build`
Expected: vitest 全绿（原 28 + 新增 2 = **30 passed**）；build 成功（`✓ built`）

- [ ] **Step 3: 更新 README 与 PROGRESS.md**

README 功能清单「管理端」加一行：`- 采集页数控制：采集源可配置采集页数（1/3/5/10/全部，全部封顶 50 页）`；测试数字更新。

PROGRESS.md「采集页数控制器」段落补「已完成 ✅」+ 6 个 commit + 后端/前端测试数字 + 真跑验收结论。

- [ ] **Step 4: 容器 rebuild 真跑验证**

```bash
docker compose build collector frontend
docker compose up -d
```

真跑：建一个 `max_pages=3` 的 gzhu 源 → 触发采集 → 断言文档数 > 单页（≈ 3 页条数）且无重复 doc_id；`max_pages=1` 源仍只采一页；存量源（无 max_pages）行为不变。

- [ ] **Step 5: Commit + push**

```bash
git add README.md docs/PROGRESS.md
git commit -m "docs: 采集页数控制器完成(后端/前端测试数字)+README/PROGRESS同步"
git push origin main
```
