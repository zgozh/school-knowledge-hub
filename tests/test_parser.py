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
