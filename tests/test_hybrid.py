from datetime import datetime, timedelta

from qa_api.retriever.hybrid import ScoredChunk, apply_expired_penalty, apply_time_decay, fuse_scores


def test_time_decay_half_life_30d():
    now = datetime(2026, 9, 1)
    pub = datetime(2026, 8, 2)  # 30 天前
    factor = apply_time_decay(pub.strftime("%Y-%m-%d"), now, half_life_days=30)
    assert abs(factor - 0.5) < 1e-6
    fresh = now - timedelta(days=1)
    assert apply_time_decay(fresh.strftime("%Y-%m-%d"), now, half_life_days=30) > 0.9


def test_time_decay_ignores_missing_date():
    assert apply_time_decay("", datetime(2026, 9, 1), half_life_days=30) == 1.0


def test_expired_penalty_applied():
    chunk = ScoredChunk(chunk_id="d_0", doc_id="d", text="t", score=0.9,
                        dense_score=0.9, sparse_score=0.9, category="通知公告",
                        topics=[], publish_date="2026-08-01", expire_at="2026-08-10",
                        status="expired", expired=False)
    penalized = apply_expired_penalty(chunk, 0.25)
    assert penalized.expired is True
    assert abs(penalized.score - 0.9 * 0.25) < 1e-9


def test_norm_score_fusion():
    dense_scores = [0.7, 0.3]
    sparse_scores = [0.5, 0.9]
    fused = fuse_scores(dense_scores, sparse_scores, dense_weight=0.8, sparse_weight=0.2)
    # min-max 归一化后：dense=[1.0,0.0] sparse=[0.0,1.0]
    # 融合：[0.8, 0.2]
    assert abs(fused[0] - 0.8) < 1e-9
    assert abs(fused[1] - 0.2) < 1e-9
