from datetime import datetime

from collector.lifecycle.validity import infer_expiry, is_expired


def test_infer_from_deadline_text():
    assert infer_expiry("关于2026年挑战杯报名通知", "报名截止时间为2026年9月15日", "通知公告", "2026-08-01") == "2026-09-15"


def test_infer_from_validity_text():
    assert infer_expiry("图书馆服务调整公告", "本公告有效期至2026年12月31日", "通知公告", "2026-08-01") == "2026-12-31"


def test_default_for_notice():
    assert infer_expiry("关于暑假放假安排的通知", "全校各单位：暑假自7月15日起。", "通知公告", "2026-06-20") == "2026-09-18"


def test_none_for_guide():
    assert infer_expiry("本科生转专业申请办理流程", "第一步：提交申请材料。", "办事指南", "2026-01-01") is None


def test_is_expired():
    assert is_expired("2026-08-01", datetime(2026, 9, 1))
    assert not is_expired("2026-08-01", datetime(2026, 7, 1))
    assert not is_expired(None, datetime(2026, 9, 1))
