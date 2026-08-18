"""一级分类：规则打标（来源栏目映射 + 标题关键词）。"""

CATEGORIES = ["通知公告", "办事指南", "规章制度", "新闻动态"]

RULE_KEYWORDS = {
    "通知公告": ["通知", "公告", "公示", "通告", "安排"],
    "办事指南": ["指南", "流程", "办事", "办理", "申请", "须知"],
    "规章制度": ["规定", "办法", "制度", "条例", "细则", "章程"],
}

COLUMN_TO_CATEGORY = {
    "通知公告": "通知公告",
    "新闻动态": "新闻动态",
}


def classify_category(title: str, column: str) -> str:
    """栏目映射优先；其次标题关键词；兜底新闻动态。"""
    if column in COLUMN_TO_CATEGORY:
        return COLUMN_TO_CATEGORY[column]
    for category, words in RULE_KEYWORDS.items():
        if any(w in title for w in words):
            return category
    return "新闻动态"
