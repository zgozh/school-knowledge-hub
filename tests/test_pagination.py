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

NEWS_NEXT_HTML = """
<html><body><ul><li><a href="info/1043/5001.htm">文章</a></li></ul>
<div class="pages"><a href="ttgd/2.htm" class="Next">下页</a></div></body></html>
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
    assert GUNewsAdapter().next_page_url(NEWS_NEXT_HTML, "https://news.gzhu.edu.cn/ttgd.htm") \
        == "https://news.gzhu.edu.cn/ttgd/2.htm"
