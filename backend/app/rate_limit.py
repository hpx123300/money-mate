"""轻量限流：固定窗口计数器，Redis 优先、内存兜底。

用于 AI 接口，防止同一用户频繁调用 LLM 产生高额成本。
"""

import time

from fastapi import HTTPException, status

from .cache import cache


def rate_limit(user_id: int, key: str, limit: int, window: int = 60) -> None:
    """固定窗口限流：每 window 秒内最多 limit 次请求，超限返回 429。

    Args:
        user_id: 当前用户 ID
        key: 限流维度（如 "ai_parse"）
        limit: 窗口内最大次数
        window: 窗口大小（秒）
    """
    cache_key = f"ratelimit:{key}:{user_id}:{int(time.time()) // window}"
    current = cache.get_json(cache_key)
    count = current if isinstance(current, int) else 0
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求太频繁，每 {window} 秒限 {limit} 次，请稍后再试",
        )
    cache.set_json(cache_key, count + 1, ttl=window)
