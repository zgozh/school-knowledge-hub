from collector.tagger.rules import classify_category


def test_classify_notice():
    assert classify_category("关于2026年暑假放假安排的通知", "通知公告") == "通知公告"
    assert classify_category("关于给予曾玮等14名学生退学处理的预公告", "通知公告") == "通知公告"


def test_classify_guide():
    assert classify_category("本科生转专业申请办理流程", "未知栏目") == "办事指南"


def test_classify_regulation():
    assert classify_category("广州大学学生住宿管理办法", "未知栏目") == "规章制度"


def test_classify_news_fallback():
    assert classify_category("我校荣获2026年教学成果一等奖", "新闻动态") == "新闻动态"
