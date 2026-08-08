"""
缓存模块（双模式）：
- 配置了 REDIS_URL 时使用 Redis（生产）
- 没配置时自动降级为进程内内存缓存（本地开发零依赖）

知识点：
1. 为什么要缓存：统计接口每次都要扫全表求和，数据多了会慢；
   把结果缓存起来，相同请求直接返回，快到毫秒级
2. 缓存一致性：设短 TTL（60 秒）+ 记账/改账时主动清掉该用户的缓存
3. Redis 是内存数据库，适合这种"热点读多写少"的场景
"""

import json
import time

from .config import settings


class MemoryCache:
    """进程内缓存：{key: (expire_at, value)}，过期自动丢弃。"""

    def __init__(self):
        self._data: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> str | None:
        item = self._data.get(key)
        if not item:
            return None
        expire_at, value = item
        if time.time() > expire_at:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, ttl: int) -> None:
        self._data[key] = (time.time() + ttl, value)

    def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self._data if k.startswith(prefix)]:
            self._data.pop(key, None)


class Cache:
    """统一缓存接口：Redis 优先，内存兜底。"""

    def __init__(self):
        self._redis = None
        if settings.redis_url:
            try:
                import redis

                self._redis = redis.Redis.from_url(
                    settings.redis_url, decode_responses=True
                )
                self._redis.ping()
                print(f"[Cache] 已连接 Redis：{settings.redis_url}")
            except Exception:
                self._redis = None
                print("[Cache] Redis 连接失败，降级为内存缓存")
        self._mem = MemoryCache()

    @property
    def backend(self) -> str:
        return "redis" if self._redis else "memory"

    def get_json(self, key: str):
        raw = self._redis.get(key) if self._redis else self._mem.get(key)
        return json.loads(raw) if raw else None

    def set_json(self, key: str, obj, ttl: int = 60) -> None:
        raw = json.dumps(obj, ensure_ascii=False)
        if self._redis:
            self._redis.setex(key, ttl, raw)
        else:
            self._mem.set(key, raw, ttl)

    def delete_prefix(self, prefix: str) -> None:
        """清除某用户的所有统计缓存（记账/改账后调用，保证数据不脏）。"""
        if self._redis:
            keys = list(self._redis.scan_iter(match=f"{prefix}*"))
            if keys:
                self._redis.delete(*keys)
        else:
            self._mem.delete_prefix(prefix)


# 全局唯一的缓存实例
cache = Cache()
