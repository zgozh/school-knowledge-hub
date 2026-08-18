"""广州大学主站适配器（www.gzhu.edu.cn 通知公告等栏目）。"""
import re

from selectolax.parser import HTMLParser

from collector.crawler.base import ArticleRef, RawArticle, SiteAdapter


class GUZhuAdapter(SiteAdapter):
    site = "gzhu"

    def parse_list(self, html: str, base_url: str) -> list[ArticleRef]:
        tree = HTMLParser(html)
        refs: list[ArticleRef] = []
        # 注：selectolax 的 css() 对逗号选择器列表不去重（同一节点匹配多个选择器会重复返回），
        # 而 div.list_news li / ul.news_list li 均为 li 的子集，故直接用单个 li 选择器等价实现。
        for li in tree.css("li"):
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
