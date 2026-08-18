"""昂贵资源客户端单例（Milvus/Mongo/MinIO/LLM 主备）。"""
from functools import lru_cache

from minio import Minio
from motor.motor_asyncio import AsyncIOMotorClient
from openai import AsyncOpenAI
from pymilvus import MilvusClient

from shared.config import settings


@lru_cache(maxsize=1)
def get_milvus() -> MilvusClient:
    return MilvusClient(uri=settings.milvus_uri)


@lru_cache(maxsize=1)
def get_mongo() -> AsyncIOMotorDatabase:
    client = AsyncIOMotorClient(settings.mongo_uri)
    return client["school_knowledge_hub"]


@lru_cache(maxsize=1)
def get_minio() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


@lru_cache(maxsize=1)
def get_llm() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


@lru_cache(maxsize=1)
def get_llm_backup() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)
