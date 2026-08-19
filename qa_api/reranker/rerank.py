"""精排：bge-reranker-large 交叉编码器；失败降级原序返回。"""
import httpx

from qa_api.retriever.hybrid import ScoredChunk
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("qa_api.reranker")


def rerank_chunks(query: str, chunks: list[ScoredChunk], client=None) -> list[ScoredChunk]:
    if not chunks:
        return chunks
    try:
        # 冷启动首次推理较慢，用 LLM 级超时（30s）而非通用外部超时（10s）
        client = client or httpx.Client(timeout=settings.llm_timeout)
        resp = client.post(f"{settings.rerank_service_url}/rerank",
                           json={"query": query, "documents": [c.text for c in chunks]})
        resp.raise_for_status()
        data = resp.json()
        scores = data["scores"]
        for c, s in zip(chunks, scores):
            c.score = s
        chunks.sort(key=lambda c: -c.score)
        return chunks
    except Exception as e:
        logger.warning("重排服务不可用，降级为检索原序: %s", e)
        return chunks
