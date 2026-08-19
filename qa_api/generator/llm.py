"""LLM 流式生成：DeepSeek 主 + DashScope 降级。"""
from typing import AsyncIterator

from qa_api.generator.prompts import SYSTEM_PROMPT
from shared.clients import get_llm, get_llm_backup
from shared.config import settings
from shared.errors import ExternalServiceError
from shared.logging import get_logger

logger = get_logger("qa_api.generator")


async def _stream_from(client, query: str, context: str, history: list[dict] | None, model: str):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in (history or [])[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user",
                     "content": f"知识片段：\n{context}\n\n问题：{query}"})
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=0.3,
    )
    async for part in resp:
        delta = part.choices[0].delta.content if part.choices else None
        if delta:
            yield delta


async def stream_answer(query: str, context: str, history: list[dict] | None = None,
                        llm=None, backup=None) -> AsyncIterator[str]:
    # 客户端构造（缺密钥）也可能抛异常，必须在 try 内逐个构造，不能构造失败就整体击穿
    primary = fallback = None
    try:
        primary = llm or get_llm()
    except Exception as e:
        logger.warning("主 LLM 客户端不可用: %s", e)
    try:
        fallback = backup or get_llm_backup()
    except Exception as e:
        logger.warning("备援 LLM 客户端不可用: %s", e)
    if primary is None and fallback is None:
        raise ExternalServiceError("LLM 客户端均不可用（缺少密钥）")
    if primary is not None:
        try:
            async for delta in _stream_from(primary, query, context, history, settings.deepseek_model):
                yield delta
            return
        except Exception as e:
            logger.warning("主 LLM 失败，切降级: %s", e)
    if fallback is not None:
        try:
            async for delta in _stream_from(fallback, query, context, history, settings.dashscope_model):
                yield delta
        except Exception as e2:
            raise ExternalServiceError(f"LLM 主备均失败: {e2}") from e2
