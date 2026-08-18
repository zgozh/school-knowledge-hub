"""问答 SSE API：检索→重排→流式生成→来源引用→日志。"""
import json
import time
import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from qa_api.generator.llm import stream_answer
from qa_api.generator.prompts import build_context
from qa_api.reranker.rerank import rerank_chunks
from qa_api.retriever.hybrid import cliff_cutoff, hybrid_search
from shared.clients import get_mongo
from shared.errors import ExternalServiceError
from shared.logging import get_logger

logger = get_logger("qa_api.chat")
router = APIRouter(prefix="/api", tags=["问答"])

EMPTY_MESSAGE = "知识库中暂未找到相关内容。建议：①换个关键词再试；②联系相关职能部门（可查官网'机构设置'栏目）；③等待系统采集最新通知后重试。"


class ChatRequest(BaseModel):
    query: str
    topic: str | None = None
    history: list[dict] | None = None


@router.post("/chat")
async def chat(req: ChatRequest):
    query_id = uuid.uuid4().hex[:12]
    started = time.monotonic()

    async def event_stream():
        try:
            chunks = await hybrid_search(req.query, topics=[req.topic] if req.topic else None)
            if not chunks:
                yield {"event": "empty", "data": json.dumps({"message": EMPTY_MESSAGE}, ensure_ascii=False)}
                return
            chunks = rerank_chunks(req.query, chunks)
            chunks = cliff_cutoff(chunks)
            answer_parts: list[str] = []

            async def generate():
                async for delta in stream_answer(req.query, build_context(chunks), req.history):
                    answer_parts.append(delta)
                    yield {"event": "chunk", "data": json.dumps({"delta": delta}, ensure_ascii=False)}

            async for ev in generate():
                yield ev

            sources = []
            for c in chunks:
                doc = await get_mongo()["documents"].find_one({"doc_id": c.doc_id})
                sources.append({
                    "doc_id": c.doc_id,
                    "title": (doc or {}).get("title", ""),
                    "url": (doc or {}).get("url", ""),
                    "publish_date": c.publish_date,
                    "category": c.category,
                    "expired": c.expired,
                })
            yield {"event": "sources", "data": json.dumps({"sources": sources}, ensure_ascii=False)}
            elapsed_ms = int((time.monotonic() - started) * 1000)
            answer = "".join(answer_parts)
            try:
                await get_mongo()["qa_logs"].insert_one({
                    "query_id": query_id, "query": req.query, "answer": answer,
                    "sources": [s["url"] for s in sources], "elapsed_ms": elapsed_ms,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            except Exception as e:
                logger.warning("问答日志写入失败(降级): %s", e)
            yield {"event": "done",
                   "data": json.dumps({"query_id": query_id, "elapsed_ms": elapsed_ms,
                                       "answer_len": len(answer)}, ensure_ascii=False)}
        except ExternalServiceError as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_stream())
