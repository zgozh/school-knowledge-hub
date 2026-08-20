"""专题域规则打标测试 + 任务管线规则兜底测试。"""
from unittest.mock import AsyncMock

import pytest

from collector import tasks as tasks_mod
from collector.crawler.base import RawArticle
from collector.parser.extract import ParsedArticle
from collector.sources import SourceConfig
from collector.tagger.rules import rule_tag_topics


def test_topic_rules_match_keywords():
    assert "新生入学" in rule_tag_topics("关于2026级新生入学报到安排的通知", "新生报到时间与流程如下")
    assert "教务学籍" in rule_tag_topics("本学期选课安排", "学生登录教务系统选课")


def test_topic_rules_multi_and_empty():
    got = rule_tag_topics("港澳台学生学籍管理办法", "港澳台学生学籍注册与内地学生同等管理")
    assert "港澳生服务" in got and "教务学籍" in got
    assert rule_tag_topics("某条无关标题", "没有任何关键词的内容") == []


async def test_task_topics_fallback_to_rules_when_llm_empty(monkeypatch):
    """LLM 打标返回空（缺 key/失败）时，专题用规则兜底，不再为空。"""
    fake_engine = AsyncMock()
    fake_engine.fetch_source = AsyncMock(return_value=(
        [RawArticle(url="https://x/1.htm", title="关于新生入学宿舍申请的通知", html="<html>x</html>",
                    publish_date="2026-08-10", source_site="gzhu", column="通知公告")], [], False))
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: fake_engine)
    fake_mongo = AsyncMock()
    fake_mongo.insert_one = AsyncMock()
    fake_mongo.update_one = AsyncMock()
    fake_mongo.__getitem__.return_value = fake_mongo
    monkeypatch.setattr(tasks_mod, "get_mongo", lambda: fake_mongo)

    def fake_extract(raw):
        return ParsedArticle(url=raw.url, title=raw.title,
                             content="新生入学宿舍申请流程说明，请按通知办理", publish_date=raw.publish_date,
                             department=None, source_site=raw.source_site, column=raw.column, raw_html=raw.html)
    monkeypatch.setattr(tasks_mod, "extract_article", fake_extract)
    monkeypatch.setattr(tasks_mod, "batch_tag_topics", AsyncMock(return_value={}))  # LLM 无结果
    ingested = []
    async def fake_ingest(parsed, category, topics, expire_at):
        ingested.append((category, topics))
    monkeypatch.setattr("collector.ingest.writer.ingest_document", fake_ingest)

    source = SourceConfig(id="s1", name="主站公告", list_url="https://x/list.htm",
                          adapter="gzhu", enabled=True, interval_minutes=60)
    result = await tasks_mod.run_collection_task(source)
    assert result["status"] == "success"
    assert any("新生入学" in topics for _, topics in ingested)
