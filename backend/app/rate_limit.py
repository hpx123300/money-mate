"""轻量限流：滑动窗口，Redis 原子执行、内存兜底。

用于 AI 接口，防止同一用户频繁调用 LLM 产生高额成本。

为什么从「固定窗口」改成「滑动窗口」：

1. 固定窗口把时间切成 [0,60)、[60,120) 这样的桶，统计区间会随桶重置。
   如果在桶 A 的末尾打满 limit 次、紧接着在桶 B 的开头再打满 limit 次，
   那么任意 60 秒内实际放过了 2×limit 次——这就是边界双倍突发。
   滑动窗口统计的是「当前时刻往前推 window 秒」，区间连续右移，没有这个问题。

2. 固定窗口的常见实现是「先 get 再 set」：两个并发请求可能同时读到旧值，
   各自 +1 后写回，最终计数少于真实请求数，限流被击穿。
   这里 Redis 侧把「清理过期 + 计数 + 写入」放进一段 Lua 脚本，
   Redis 单线程执行脚本，天然原子；内存侧用 threading.Lock 保护。

3. 限流组件本身不能成为故障点：Redis 报错时自动退化为内存限流，
   而不是把请求直接打挂。
"""

import threading
import time
import uuid
from collections import deque

from fastapi import HTTPException, status

from .cache import cache

# 滑动窗口：ZSET 存每次请求的时间戳，先按分数剔除窗口外的记录，再数剩下的。
# 返回 1 表示放行、0 表示超限。整段脚本在 Redis 内原子执行。
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window_ms)
local count = redis.call('ZCARD', key)
if count >= limit then
  return 0
end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window_ms)
return 1
"""

_script = None
_script_lock = threading.Lock()


class MemoryWindow:
    """进程内滑动窗口：每个 key 一个时间戳队列，过期即出队。

    FastAPI 的同步接口跑在线程池里，多个线程会同时读写同一个 key，
    所以「清理 + 判断 + 记录」必须在同一把锁内完成。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, limit: int, window: float, now: float | None = None) -> bool:
        """是否放行；now 可显式传入，便于测试构造窗口边界场景。"""
        moment = time.monotonic() if now is None else now
        cutoff = moment - window
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(moment)
            # 只被拒绝过的 key 会留下空队列，顺手清掉，避免无限增长
            if len(self._hits) > 1024:
                for stale in [k for k, v in self._hits.items() if not v]:
                    self._hits.pop(stale, None)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


memory_window = MemoryWindow()


def _redis_allow(client, key: str, limit: int, window: int) -> bool:
    """在 Redis 里原子执行滑动窗口判断。"""
    global _script
    if _script is None:
        with _script_lock:
            if _script is None:
                _script = client.register_script(_SLIDING_WINDOW_LUA)
    now_ms = int(time.time() * 1000)
    # 同一毫秒内的多次请求需要不同的 member，否则 ZSET 会去重、少算次数
    result = _script(keys=[key], args=[now_ms, int(window * 1000), limit, uuid.uuid4().hex])
    return bool(result)


def rate_limit(user_id: int, key: str, limit: int, window: int = 60) -> None:
    """滑动窗口限流：最近 window 秒内最多 limit 次请求，超限抛 429。

    Args:
        user_id: 当前用户 ID
        key: 限流维度（如 "ai_parse"），不同维度各自独立计数
        limit: 窗口内最大次数
        window: 窗口大小（秒）
    """
    cache_key = f"ratelimit:{key}:{user_id}"
    client = cache.redis
    if client is not None:
        try:
            allowed = _redis_allow(client, cache_key, limit, window)
        except Exception:
            # Redis 抖动不能让业务跟着挂：退化为进程内限流
            allowed = memory_window.allow(cache_key, limit, window)
    else:
        allowed = memory_window.allow(cache_key, limit, window)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求太频繁，{window} 秒内最多 {limit} 次，请稍后再试",
        )
