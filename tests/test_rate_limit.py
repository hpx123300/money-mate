"""限流器测试。

分三层覆盖：
1. 内存窗口的算法本身（滑动窗口语义、边界不双倍突发）——用显式时间戳，不依赖真实时钟；
2. 通过 rate_limit() 走完整路径，验证超限抛 429、窗口滑过后自动恢复；
3. Redis 分支：用 fakeredis 在进程内真正执行那段 Lua 脚本。
   本地没有 Redis，而 Redis 恰好是生产路径（docker-compose 就配了 REDIS_URL），
   不验证等于把没跑过的代码发上线。
"""

import time

import fakeredis
import pytest
from fastapi import HTTPException

from app import rate_limit as rl
from app.cache import cache
from app.rate_limit import MemoryWindow


# ---------------- 一、内存窗口的算法 ----------------

def test_memory_window_allows_up_to_limit():
    w = MemoryWindow()
    for _ in range(3):
        assert w.allow("k", limit=3, window=60, now=0.0) is True
    assert w.allow("k", limit=3, window=60, now=0.0) is False


def test_memory_window_has_no_boundary_double_burst():
    """固定窗口在整秒处换桶，边界两侧能各放 limit 次；滑动窗口不应该有这个问题。"""
    w = MemoryWindow()
    # 窗口 1 秒、限 2 次：在 0.9 秒附近打满
    assert w.allow("k", 2, 1.0, now=0.90) is True
    assert w.allow("k", 2, 1.0, now=0.95) is True
    # 跨过固定窗口的 1.0 秒边界，仍然应该被拒——0.90 那次还在 1 秒窗口内
    assert w.allow("k", 2, 1.0, now=1.00) is False
    # 等 0.90 那次滑出窗口后才恢复
    assert w.allow("k", 2, 1.0, now=1.91) is True


def test_memory_window_keys_are_independent():
    w = MemoryWindow()
    assert w.allow("a", 1, 60, now=0.0) is True
    assert w.allow("b", 1, 60, now=0.0) is True
    assert w.allow("a", 1, 60, now=0.0) is False


# ---------------- 二、完整路径（内存分支） ----------------

def test_rate_limit_raises_429_then_recovers():
    key = f"unittest-{time.time_ns()}"
    for _ in range(2):
        rl.rate_limit(1, key, limit=2, window=1)

    with pytest.raises(HTTPException) as exc:
        rl.rate_limit(1, key, limit=2, window=1)
    assert exc.value.status_code == 429

    time.sleep(1.05)  # 等窗口滑过去
    rl.rate_limit(1, key, limit=2, window=1)


def test_rate_limit_isolates_user_and_dimension():
    key = f"unittest-{time.time_ns()}"
    rl.rate_limit(1, key, limit=1, window=60)
    rl.rate_limit(2, key, limit=1, window=60)  # 另一个用户，互不影响
    rl.rate_limit(1, f"{key}-other", limit=1, window=60)  # 另一个限流维度，互不影响

    with pytest.raises(HTTPException):
        rl.rate_limit(1, key, limit=1, window=60)


# ---------------- 三、Redis 分支（Lua 脚本） ----------------

@pytest.fixture
def fake_redis(monkeypatch):
    """把限流器切到 Redis 分支，用 fakeredis 在进程内执行 Lua。"""
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "_redis", client)
    # 脚本对象缓存会绑定创建它的客户端，换客户端前必须清掉
    monkeypatch.setattr(rl, "_script", None)
    return client


def _redis_key(dim: str, user_id: int) -> str:
    return f"ratelimit:{dim}:{user_id}"


def test_redis_branch_enforces_limit(fake_redis):
    dim = f"redis-{time.time_ns()}"
    for _ in range(3):
        rl.rate_limit(7, dim, limit=3, window=60)

    with pytest.raises(HTTPException) as exc:
        rl.rate_limit(7, dim, limit=3, window=60)
    assert exc.value.status_code == 429


def test_redis_branch_window_expires(fake_redis):
    dim = f"redis-{time.time_ns()}"
    rl.rate_limit(8, dim, limit=1, window=1)
    with pytest.raises(HTTPException):
        rl.rate_limit(8, dim, limit=1, window=1)

    time.sleep(1.05)
    rl.rate_limit(8, dim, limit=1, window=1)


def test_redis_records_one_member_per_request(fake_redis):
    """ZSET 的 member 必须每次唯一，否则同一毫秒内的并发会被去重、少算次数。"""
    dim = f"unique-{time.time_ns()}"
    rl.rate_limit(11, dim, limit=10, window=60)
    rl.rate_limit(11, dim, limit=10, window=60)

    assert fake_redis.zcard(_redis_key(dim, 11)) == 2


def test_redis_sets_ttl_so_keys_do_not_pile_up(fake_redis):
    dim = f"ttl-{time.time_ns()}"
    rl.rate_limit(13, dim, limit=5, window=60)
    assert fake_redis.ttl(_redis_key(dim, 13)) > 0


def test_redis_failure_degrades_to_memory(monkeypatch):
    """Redis 抖动不能让业务跟着挂：应退化为进程内限流，而不是抛异常。"""

    class Broken:
        def register_script(self, *_args, **_kwargs):
            raise RuntimeError("redis 连接断了")

    monkeypatch.setattr(cache, "_redis", Broken())
    monkeypatch.setattr(rl, "_script", None)

    dim = f"fallback-{time.time_ns()}"
    rl.rate_limit(12, dim, limit=1, window=60)  # 不抛异常即为降级成功

    with pytest.raises(HTTPException) as exc:
        rl.rate_limit(12, dim, limit=1, window=60)
    assert exc.value.status_code == 429  # 降级后限流依然生效
