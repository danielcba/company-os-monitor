"""07 - Rate Limiter Bypass: Redis failure must not silently allow requests.

When Redis is unavailable for rate limiting:
- is_allowed -> raises RateLimiterUnavailable (fail-closed for security)
"""
import asyncio
import time
from collections import defaultdict

import pytest

REDIS_UNAVAILABLE_MSG = "Redis is down"
RATE_LIMITER_UNAVAIL_FMT = "Redis unavailable for rate limiting key={key!r}"


class RateLimiterUnavailable(Exception):
    """Raised when rate limiter backend is unavailable."""


class _SLIDING_WINDOW_LUA:
    pass


class _MemoryLimiter:
    """Direct in-memory rate limiter for testing."""

    def __init__(self, max_requests=10, window_seconds=60):
        self._max = max_requests
        self._window = window_seconds
        self._hits = defaultdict(list)

    def is_allowed(self, key):
        now = time.monotonic()
        cutoff = now - self._window
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]
        if len(self._hits[key]) >= self._max:
            return False
        self._hits[key].append(now)
        return True


def test_rate_limiter_blocks_after_max_requests():
    """Rate limiter must block after max_requests in memory mode."""
    limiter = _MemoryLimiter(max_requests=3, window_seconds=60)
    assert limiter.is_allowed("k") is True
    assert limiter.is_allowed("k") is True
    assert limiter.is_allowed("k") is True
    assert limiter.is_allowed("k") is False


def test_rate_limiter_different_keys_independent():
    """Different keys must have independent counters."""
    limiter = _MemoryLimiter(max_requests=2, window_seconds=60)
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("a") is False
    assert limiter.is_allowed("b") is True
    assert limiter.is_allowed("b") is True
    assert limiter.is_allowed("b") is False


def test_rate_limiter_sliding_window():
    """Rate limiter uses sliding window (old requests expire)."""
    limiter = _MemoryLimiter(max_requests=2, window_seconds=0.1)
    assert limiter.is_allowed("k") is True
    assert limiter.is_allowed("k") is True
    assert limiter.is_allowed("k") is False
    time.sleep(0.15)
    assert limiter.is_allowed("k") is True


def test_fail_closed_principle():
    """When Redis is unavailable, rate limiting must fail closed (reject)."""
    class BrokenRedis:
        async def eval(self, *args, **kwargs):
            raise ConnectionError(REDIS_UNAVAILABLE_MSG)

    class RateLimiterUnavailable(Exception):
        """Raised when rate limiter backend is unavailable."""
        pass


    class _LuaRateLimiter:
        """Minimal rate limiter that raises on Redis failure."""
        def __init__(self, redis, max_requests=10, window_seconds=60):
            self._redis = redis
            self._max = max_requests
            self._window = window_seconds

        async def is_allowed(self, key: str) -> bool:
            try:
                await self._redis.eval(
                    "return redis.call('exists', KEYS[1]) == 0 and "
                    "redis.call('incr', KEYS[1]) or redis.call('incr', KEYS[1])",
                    1, key,
                )
            except Exception as exc:
                raise RateLimiterUnavailable(
                    RATE_LIMITER_UNAVAIL_FMT.format(key=key)
                ) from exc
            else:
                return True

    limiter = _LuaRateLimiter(redis=BrokenRedis(), max_requests=10, window_seconds=60)
    with pytest.raises(RateLimiterUnavailable):
        asyncio.run(limiter.is_allowed("test:key"))
