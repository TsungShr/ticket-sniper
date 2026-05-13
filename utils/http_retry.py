"""HTTP 重试工具 — 为 aiohttp 请求添加指数退避重试"""
import asyncio
import logging
from functools import wraps
from typing import Awaitable, Callable, ParamSpec, TypeVar

import aiohttp
from aiohttp import ClientSession
from aiohttp_retry import ExponentialBackoffRetryOptions, RetryClient

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry_options(
    max_retries: int = 2,
    initial_delay: float = 0.1,
    max_delay: float = 2.0,
    jitter: bool = True,
) -> ExponentialBackoffRetryOptions:
    """构造指数退避重试选项，默认最多 3 次（首次 + 2 次重试）"""
    return ExponentialBackoffRetryOptions(
        backoff_factor=initial_delay,
        max_time=max_delay,
        max_retries=max_retries,
        jitter=jitter,
    )


def make_retry_session(session: ClientSession, **kwargs) -> RetryClient:
    """将已有 session 包装为支持重试的 RetryClient"""
    return RetryClient(session, retry_options=retry_options())


def with_retry(max_retries: int = 2):
    """装饰器：为协程函数添加指数退避重试

    仅在遇到 aiohttp.ClientError 时重试。成功响应或业务错误（如 statusCode != 200）
    不会被重试，由调用方自行处理。
    """
    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except aiohttp.ClientError as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = 0.1 * (2 ** attempt)
                        logger.warning(
                            f"{fn.__name__} 第 {attempt + 1} 次失败: {e}，"
                            f" {delay:.1f}s 后重试..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"{fn.__name__} 全部 {max_retries + 1} 次尝试均失败")
            raise RuntimeError(f"{fn.__name__} 重试耗尽") from last_exc
        return wrapper
    return decorator
