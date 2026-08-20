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
