"""混合检索：dense+sparse 双路召回 → norm_score 融合 → 时间衰减 → 过期降权。"""
import httpx
from dataclasses import dataclass, field
from datetime import datetime

from shared.config import settings
from shared.logging import get_logger

logger = get_logger("qa_api.retriever")


@dataclass
class ScoredChunk:
    chunk_id: str
    doc_id: str
    text: str
    score: float
    dense_score: float
    sparse_score: float
    category: str = ""
    topics: list = field(default_factory=list)
    publish_date: str = ""
    expire_at: str = ""
    status: str = "active"
    expired: bool = False


def minmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def fuse_scores(dense_scores: list[float], sparse_scores: list[float],
                dense_weight: float, sparse_weight: float) -> list[float]:
    nd = minmax(dense_scores)
    ns = minmax(sparse_scores)
    return [dense_weight * d + sparse_weight * s for d, s in zip(nd, ns)]


def apply_time_decay(publish_date: str, now: datetime, half_life_days: float) -> float:
    if not publish_date:
        return 1.0
    try:
        pub = datetime.strptime(publish_date, "%Y-%m-%d")
    except ValueError:
        return 1.0
    days = max((now - pub).days, 0)
    return 0.5 ** (days / half_life_days)


def apply_expired_penalty(chunk: ScoredChunk, penalty: float) -> ScoredChunk:
    expired = chunk.status == "expired" or (chunk.expire_at and chunk.expire_at < datetime.now().strftime("%Y-%m-%d"))
    if expired:
        chunk.expired = True
        chunk.score *= penalty
    return chunk


def _embed_query(query: str) -> dict:
    resp = httpx.post(f"{settings.embed_service_url}/embed", json={"texts": [query]},
                      timeout=settings.external_timeout)
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


def _search_one(milvus, emb: dict, vector_field: str, metric: str, top_k: int, expr: str | None):
    query_vec = emb["dense"] if vector_field == "dense_vector" else emb["sparse"]
    results = milvus.search(
        collection_name=settings.milvus_collection,
        data=[query_vec],
        anns_field=vector_field,
        limit=top_k,
        filter=expr or "",
        output_fields=["doc_id", "chunk_idx", "text", "category", "topics",
                       "publish_date", "expire_at", "status"],
        search_params={"metric_type": metric, "params": {"nprobe": 16}},
    )
    return results[0] if results else []


async def hybrid_search(query: str, category: str | None = None, topics: list[str] | None = None,
                        top_k: int | None = None, milvus=None, embed_fn=None) -> list[ScoredChunk]:
    from shared.clients import get_milvus

    milvus = milvus or get_milvus()
    top_k = top_k or settings.recall_top_k
    try:
        emb = (embed_fn or _embed_query)(query)
    except Exception as e:
        logger.warning("embedding 服务不可用: %s", e)
        return []

    expr_parts = []
    if category:
        expr_parts.append(f'category == "{category}"')
    if topics:
        topic_expr = " || ".join(f'topics like "%{t}%"' for t in topics)
        expr_parts.append(f"({topic_expr})")
    expr = " && ".join(expr_parts) or None

    # dense 必跑；sparse 失败降级为全 0（主链路可用）；过滤表达式失败降级为无过滤重试
    try:
        dense_hits = _search_one(milvus, emb, "dense_vector", "COSINE", top_k, expr)
    except Exception as e:
        if expr is not None:
            logger.warning("过滤表达式执行失败，降级无过滤检索: %s", e)
            expr = None
            try:
                dense_hits = _search_one(milvus, emb, "dense_vector", "COSINE", top_k, expr)
            except Exception as e2:
                logger.warning("dense 检索异常: %s", e2)
                return []
        else:
            logger.warning("dense 检索异常: %s", e)
            return []
    try:
        sparse_hits = _search_one(milvus, emb, "sparse_vector", "IP", top_k, expr)
    except Exception as e:
        logger.warning("sparse 检索异常，降级仅 dense: %s", e)
        sparse_hits = []

    # 以 chunk_id 对齐两路结果
    dense_map = {h["id"]: h for h in dense_hits}
    sparse_map = {h["id"]: h for h in sparse_hits}
    keys = list(dict.fromkeys([h["id"] for h in dense_hits] + [h["id"] for h in sparse_hits]))
    dense_scores = [dense_map[k]["distance"] if k in dense_map else 0.0 for k in keys]
    sparse_scores = [sparse_map[k]["distance"] if k in sparse_map else 0.0 for k in keys]
    fused = fuse_scores(dense_scores, sparse_scores, settings.dense_weight, settings.sparse_weight)

    now = datetime.now()
    chunks: list[ScoredChunk] = []
    for k, score in zip(keys, fused):
        h = dense_map.get(k) or sparse_map[k]
        entity = h.get("entity", h)
        chunk = ScoredChunk(
            chunk_id=k, doc_id=entity.get("doc_id", ""), text=entity.get("text", ""),
            score=score, dense_score=dense_map[k]["distance"] if k in dense_map else 0.0,
            sparse_score=sparse_map[k]["distance"] if k in sparse_map else 0.0,
            category=entity.get("category", ""), topics=entity.get("topics", []),
            publish_date=entity.get("publish_date", ""), expire_at=entity.get("expire_at", ""),
            status=entity.get("status", "active"),
        )
        chunk.score *= apply_time_decay(chunk.publish_date, now, settings.time_decay_half_life_days)
        chunk = apply_expired_penalty(chunk, settings.expired_penalty)
        chunks.append(chunk)

    chunks.sort(key=lambda c: -c.score)
    return chunks[:top_k]


def cliff_cutoff(chunks: list[ScoredChunk], ratio: float | None = None) -> list[ScoredChunk]:
    """断崖截断：相邻分数骤降（跌幅超过 ratio）即截断。至少保留 1 条。"""
    ratio = settings.cliff_cutoff_ratio if ratio is None else ratio
    if not chunks:
        return []
    kept = [chunks[0]]
    for prev, cur in zip(chunks, chunks[1:]):
        if cur.score < prev.score * (1 - ratio):
            break
        kept.append(cur)
    return kept
