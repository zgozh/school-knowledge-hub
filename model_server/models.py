"""FlagEmbedding 模型加载：BGE-M3（dense+sparse）与 bge-reranker-large。"""
from functools import lru_cache

from FlagEmbedding import BGEM3FlagModel, FlagReranker

from shared.config import settings


@lru_cache(maxsize=1)
def get_bge_m3() -> BGEM3FlagModel:
    return BGEM3FlagModel(settings.bge_m3_path, use_fp16=True)


@lru_cache(maxsize=1)
def get_reranker() -> FlagReranker:
    return FlagReranker(settings.reranker_path, use_fp16=True)
