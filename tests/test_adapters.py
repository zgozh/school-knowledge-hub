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
