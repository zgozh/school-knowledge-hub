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
    articles, failures, _ = await engine.fetch_source("https://x/list.htm", adapter)
    assert len(articles) == 2
    assert failures == []
    # 第二轮：全部已见，无新文章
    articles2, _, _ = await engine.fetch_source("https://x/list.htm", adapter)
    assert articles2 == []


async def test_engine_isolates_page_failure():
    adapter = FakeAdapter()
    adapter.fail_url = "https://x/info/1.htm"
    engine = CrawlEngine(http_client=FakeHTTP())
    articles, failures, _ = await engine.fetch_source("https://x/list.htm", adapter)
    assert len(articles) == 1
    assert len(failures) == 1
    assert failures[0]["url"] == "https://x/info/1.htm"
