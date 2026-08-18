"""全局配置：.env → dataclass 单例。"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # 存储
    milvus_uri: str = os.getenv("MILVUS_URI", "http://localhost:19530")
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "school-knowledge-hub")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    # LLM
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    dashscope_model: str = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
    # 模型服务
    embed_service_url: str = os.getenv("EMBED_SERVICE_URL", "http://localhost:8001")
    rerank_service_url: str = os.getenv("RERANK_SERVICE_URL", "http://localhost:8001")
    bge_m3_path: str = os.getenv("BGE_M3_PATH", "/models/bge-m3")
    reranker_path: str = os.getenv("RERANKER_PATH", "/models/bge-reranker-large")
    # Milvus
    milvus_collection: str = os.getenv("MILVUS_COLLECTION", "school_docs")
    # 检索参数（ADR-006）
    dense_weight: float = float(os.getenv("DENSE_WEIGHT", "0.8"))
    sparse_weight: float = float(os.getenv("SPARSE_WEIGHT", "0.2"))
    recall_top_k: int = int(os.getenv("RECALL_TOP_K", "10"))
    time_decay_half_life_days: float = float(os.getenv("TIME_DECAY_HALF_LIFE_DAYS", "30"))
    expired_penalty: float = float(os.getenv("EXPIRED_PENALTY", "0.25"))
    cliff_cutoff_ratio: float = float(os.getenv("CLIFF_CUTOFF_RATIO", "0.3"))
    # 端口
    collector_port: int = int(os.getenv("COLLECTOR_PORT", "8002"))
    qa_api_port: int = int(os.getenv("QA_API_PORT", "8003"))
    # 通用
    external_timeout: float = float(os.getenv("EXTERNAL_TIMEOUT", "10"))
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "30"))


settings = Settings()
