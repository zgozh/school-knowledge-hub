"""爬虫引擎：异步抓取列表页与详情页，增量去重，单页失败隔离。"""
import asyncio

import httpx

from collector.crawler.base import RawArticle, SiteAdapter
from collector.dedup import content_hash, url_hash
from shared.config import settings
from shared.errors import ExternalServiceError
from shared.logging import get_logger

logger = get_logger("collector.engine")

MAX_PAGES_CAP = 50


class CrawlEngine:
    # 站点 WAF 拦截默认 python-httpx UA，统一伪装浏览器（否则 403）
    DEFAULT_HEADERS = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._http = http_client or httpx.AsyncClient(
            timeout=settings.external_timeout, headers=self.DEFAULT_HEADERS)
        self._seen: set[str] = set()

    def has_seen(self, key: str) -> bool:
        return key in self._seen

    def set_seen(self, key: str) -> None:
        self._seen.add(key)

    async def fetch_source(self, list_url: str, adapter: SiteAdapter, max_pages: int = 1) \
            -> tuple[list[RawArticle], list[dict], bool]:
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
                # 注：计划原文未隔离 parse_detail 异常，单页解析失败会击穿整个 fetch_source；
                # 按「单页失败隔离」契约补上同款隔离（记入失败清单，不中断其余页面）。
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

    async def close(self) -> None:
        await self._http.aclose()
