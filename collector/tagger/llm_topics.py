"""二级专题域：LLM 批量打标（可离线批处理，失败返回空由规则兜底）。"""
import json
import re

from collector.parser.extract import ParsedArticle
from shared.clients import get_llm
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("collector.tagger")

TOPICS = ["新生入学", "港澳生服务", "教务学籍", "后勤生活", "就业创业", "科研学术"]

TOPIC_PROMPT = """你是校务知识打标助手。给每篇文章从下列专题域中选择最相关的（可多选、可空）：
专题域：{topics}
文章列表（编号|标题|摘要）：
{items}

只输出 JSON：{{"<编号>": ["专题域1", ...]}}"""


async def batch_tag_topics(articles: list[ParsedArticle], llm=None) -> dict[str, list[str]]:
    """返回 {url: [topics]}；失败返回空 dict（规则兜底）。"""
    if not articles:
        return {}
    items = "\n".join(f"{i}|{a.title}|{a.content[:80]}" for i, a in enumerate(articles))
    prompt = TOPIC_PROMPT.format(topics=",".join(TOPICS), items=items)
    try:
        client = llm or get_llm()
        resp = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = resp.choices[0].message.content or "{}"
        m = re.search(r"\{.*\}", content, re.S)
        data = json.loads(m.group(0)) if m else {}
        result: dict[str, list[str]] = {}
        for key, topics in data.items():
            if key.isdigit() and int(key) < len(articles):
                valid = [t for t in topics if t in TOPICS]
                if valid:
                    result[articles[int(key)].url] = valid
        return result
    except Exception as e:
        logger.warning("专题域 LLM 打标失败，规则兜底: %s", e)
        return {}
