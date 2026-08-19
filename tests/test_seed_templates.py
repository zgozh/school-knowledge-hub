"""模拟数据模板库测试：六大专题域全覆盖、字段完整、与规则词表一致。"""
from collector.tagger.llm_topics import TOPICS
from collector.tagger.rules import CATEGORIES, classify_category, rule_tag_topics
from scripts.demo_templates import DEMO_ARTICLES


def test_templates_cover_all_six_topics():
    assert {t.topic for t in DEMO_ARTICLES} == set(TOPICS)


def test_each_topic_has_at_least_three_articles():
    for topic in TOPICS:
        assert sum(1 for t in DEMO_ARTICLES if t.topic == topic) >= 3


def test_templates_valid_and_consistent_with_rules():
    assert len(DEMO_ARTICLES) >= 18
    urls = set()
    for t in DEMO_ARTICLES:
        assert t.title and len(t.content) >= 50, f"{t.title} 正文过短"
        assert t.topic in TOPICS and t.category in CATEGORIES
        assert t.publish_date and t.department and t.column
        # 规则必须把模板归到其声明分类（保证播种管线产出确定性）
        assert classify_category(t.title, t.column) == t.category, f"{t.title} 分类不一致"
        # 规则必须命中其声明专题（保证专题非空）
        assert t.topic in rule_tag_topics(t.title, t.content), f"{t.title} 专题不一致"
        # filename 唯一
        filename = f"{t.topic}-{t.title[:8]}"
        assert filename not in urls
        urls.add(filename)
