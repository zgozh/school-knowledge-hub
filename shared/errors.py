"""异常基类体系：业务层只抛业务异常。"""


class AppError(Exception):
    """应用异常基类。"""


class ExternalServiceError(AppError):
    """外部服务（Milvus/Mongo/MinIO/LLM/模型服务）调用失败。"""


class DegradedError(AppError):
    """可选依赖降级后仍无法满足请求（用于告警标记）。"""


class ValidationError(AppError):
    """输入/配置校验失败。"""
