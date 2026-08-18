"""指数退避重试装饰器（只重试外部服务错误）。"""
import asyncio
import functools

from shared.errors import ExternalServiceError


def async_retry(retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
    def deco(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except ExternalServiceError:
                    if attempt == retries - 1:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    await asyncio.sleep(delay)
        return wrapper
    return deco
