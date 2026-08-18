"""时效推断：截止日期识别 + 类别默认有效期 + 过期判定。"""
import re
from datetime import datetime, timedelta

NOTICE_DEFAULT_DAYS = 90

DEADLINE_PATTERNS = [
    r"(?:报名)?截止(?:时间|日期)?[:：]?为?\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
    r"截至\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
    r"有效期至\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
]


def infer_expiry(title: str, content: str, category: str, publish_date: str) -> str | None:
    """推断有效期截止日；无法推断且类别无默认值时返回 None。"""
    text = title + " " + content
    for pattern in DEADLINE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    if category == "通知公告":
        pub = datetime.strptime(publish_date, "%Y-%m-%d")
        return (pub + timedelta(days=NOTICE_DEFAULT_DAYS)).strftime("%Y-%m-%d")
    return None


def is_expired(expire_at: str | None, now: datetime) -> bool:
    if expire_at is None:
        return False
    return datetime.strptime(expire_at, "%Y-%m-%d") < now
