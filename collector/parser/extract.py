"""正文提取：trafilatura 为主，DeepSeek 兜底结构化提取。"""
import json
import re
from dataclasses import dataclass

import trafilatura

from collector.crawler.base import RawArticle
from shared.clients import get_llm
from shared.config import settings
from shared.errors import ExternalServiceError
from shared.logging import get_logger

logger = get_logger("collector.parser")

LLM_EXTRACT_PROMPT = """你是校务文档解析器。从下面 HTML 中提取文章信息，只输出 JSON，不要输出其他内容。
JSON 格式：{{"title": "标题", "content": "正文（纯文本，保留段落）", "publish_date": "YYYY-MM-DD 或 null", "department": "发布部门或 null"}}

HTML:
{html}"""


@dataclass
class ParsedArticle:
    url: str
    title: str
    content: str
    publish_date: str | None
    department: str | None
    source_site: str
    column: str
    raw_html: str


def extract_article(raw: RawArticle) -> ParsedArticle:
    text = trafilatura.extract(raw.html, include_comments=False, include_tables=False) or ""
    title = _extract_title(raw.html) or raw.title
    publish_date = _extract_date(raw.html) or raw.publish_date
    department = _extract_department(raw.html)
    if len(text.strip()) < 50:
        logger.warning("trafilatura 提取过短(%d字)，走 LLM 兜底: %s", len(text.strip()), raw.url)
        fallback = llm_extract(raw.html)
        text = fallback.get("content", text)
        title = fallback.get("title") or title
        publish_date = fallback.get("publish_date") or publish_date
        department = fallback.get("department") or department
    if len(text.strip()) < 20:
        raise ExternalServiceError(f"正文提取失败: {raw.url}")
    return ParsedArticle(url=raw.url, title=title, content=text.strip(),
                         publish_date=publish_date, department=department,
                         source_site=raw.source_site, column=raw.column, raw_html=raw.html)


def llm_extract(html: str) -> dict:
    client = get_llm()
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[{"role": "user", "content": LLM_EXTRACT_PROMPT.format(html=html[:20000])}],
        temperature=0,
    )
    content = resp.choices[0].message.content or "{}"
    m = re.search(r"\{.*\}", content, re.S)
    return json.loads(m.group(0)) if m else {}


def _extract_title(html: str) -> str:
    for tag in ("<h1[^>]*>(.*?)</h1>", "<title[^>]*>(.*?)</title>"):
        m = re.search(tag, html, re.S | re.I)
        if m:
            return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


def _extract_date(html: str) -> str | None:
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", html)
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def _extract_department(html: str) -> str | None:
    m = re.search(r"来源[:：]\s*([^\s<&]{2,30})", html)
    return m.group(1).strip() if m else None
