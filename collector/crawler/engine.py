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
                # 注：计划原文未隔离 parse_detail 异常，单页解析失败会击穿整个 fetch_source；
                # 按「单页失败隔离」契约补上同款隔离（记入失败清单，不中断其余页面）。
                try:
                    articles.append(adapter.parse_detail(resp.text, ref))
                except Exception as e:
                    failures.append({"url": ref.url, "error": str(e)})

        await asyncio.gather(*(fetch_one(r) for r in refs))
        return articles, failures

    async def close(self) -> None:
        await self._http.aclose()
