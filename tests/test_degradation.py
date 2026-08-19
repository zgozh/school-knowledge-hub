# tests/test_degradation.py
"""降级路径测试（spec §8 降级链契约）：reranker/LLM 主备。"""
import json

import httpx
import pytest
from openai import AsyncOpenAI

from qa_api.generator.llm import stream_answer
from qa_api.reranker.rerank import rerank_chunks
from qa_api.retriever.hybrid import ScoredChunk
from shared.config import settings
from shared.errors import ExternalServiceError


def make_chunks():
    return [ScoredChunk(chunk_id=f"c{i}", doc_id=f"d{i}", text=f"文本{i}",
                        score=s, dense_score=s, sparse_score=0.0)
            for i, s in enumerate([0.9, 0.8, 0.7])]


def test_rerank_down_falls_back_to_original_order(monkeypatch):
    monkeypatch.setattr(settings, "rerank_service_url", "http://127.0.0.1:1/rerank")
    chunks = make_chunks()
    out = rerank_chunks("查询", chunks)
    assert [c.chunk_id for c in out] == [c.chunk_id for c in chunks]  # 原序
    assert [c.score for c in out] == [0.9, 0.8, 0.7]  # 分数未改


def _sse_response(deltas):
    body = "".join(f'data: {json.dumps({"choices": [{"delta": {"content": d}}]}, ensure_ascii=False)}\n\n'
                   for d in deltas) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


def _stub_client(handler):
    return AsyncOpenAI(api_key="stub", base_url="https://stub.invalid/v1",
                       http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_llm_primary_fails_falls_back_to_backup():
    def primary_handler(request):
        return httpx.Response(500, text="primary down")

    def backup_handler(request):
        assert "/chat/completions" in request.url.path
        return _sse_response(["备", "援"])

    parts = [d async for d in stream_answer(
        "测试问题", "知识片段", llm=_stub_client(primary_handler), backup=_stub_client(backup_handler))]
    assert "".join(parts) == "备援"


async def test_llm_both_down_raises_external_error():
    def down(request):
        return httpx.Response(500, text="down")

    with pytest.raises(ExternalServiceError):
        _ = [d async for d in stream_answer(
            "测试问题", "知识片段", llm=_stub_client(down), backup=_stub_client(down))]
