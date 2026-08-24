"""Distributed sliding window rate limiter backed by Redis (atomic).

Phase 4: Atomic rate limiting using a Lua script that executes the entire
sliding window check (remove expired + count + compare + insert + expire)
in a single Redis call. No race conditions between operations.

The API is now async-native (``await limiter.is_allowed(key)``). No more
sync bridges with ThreadPoolExecutor.

Falls back to in-memory when Redis is unavailable (fail-open for availability).

Redis key pattern: ``ratelimit:{key}``
Sorted set members: ``{timestamp}:{random}`` (unique per request)
Score: request timestamp (epoch seconds, float)

Usage::

    from src.ratelimit import RateLimiter

    limiter = RateLimiter.from_url("redis://localhost:6379/1")
    if not await limiter.is_allowed(f"login:{client_ip}"):
        return 429
"""
import os
import time
import uuid
from collections import defaultdict
from typing import Protocol

# Lua script for atomic sliding window rate limit check.
# KEYS[1] = ratelimit:{key}
# ARGV[1] = now (timestamp)
# ARGV[2] = cutoff (now - window_seconds)
# ARGV[3] = max_requests
# ARGV[4] = member (unique identifier)
# ARGV[5] = ttl (window_seconds + buffer)
# Returns: 1 = allowed, 0 = denied
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])

-- Remove expired entries.
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

-- Count current window requests.
local count = redis.call('ZCARD', key)

if count >= max_requests then
    return 0
end

-- Add current request.
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, ttl)

return 1
"""


class RateLimiterUnavailable(Exception):
    """Raised when the rate limiter backend (Redis) is unavailable.

    For security-critical endpoints (login, refresh), this must result
    in request rejection (fail-closed), not silent pass-through.
    """


class RedisClient(Protocol):
    """Minimal async Redis interface for the rate limiter."""

    async def eval(
        self, script: str, num_keys: int, *args: str | int | float
    ) -> int: ...


class RateLimiter:
    """Sliding window rate limiter keyed by IP or identifier.

    Supports both Redis-backed (distributed, atomic via Lua) and
    in-memory (standalone) modes.
    """

    def __init__(
        self,
        max_requests: int | None = None,
        window_seconds: float | None = None,
        redis: RedisClient | None = None,
    ):
        self._max = max_requests or int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "10"))
        self._window = window_seconds or float(
            os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")
        )
        self._redis = redis
        self._hits: dict[str, list[float]] = defaultdict(list)

    @classmethod
    def from_url(cls, redis_url: str = "redis://localhost:6379/1") -> "RateLimiter":
        """Create a Redis-backed rate limiter."""
        try:
            from redis.asyncio import Redis

            redis = Redis.from_url(redis_url, decode_responses=True)
            return cls(redis=redis)
        except ImportError:
            return cls()

    async def is_allowed(self, key: str) -> bool:
        """Return True if the request is allowed, False if rate-limited.

        Uses Redis Lua script when available (atomic).
        Raises RateLimiterUnavailable if Redis is down (fail-closed).
        """
        if self._redis is not None:
            return await self._is_allowed_redis(key)
        return self._is_allowed_memory(key)

    async def _is_allowed_redis(self, key: str) -> bool:
        """Redis-backed sliding window check (atomic via Lua script).

        Fail-closed: raises RateLimiterUnavailable when Redis is down
        for security-critical endpoints (login, refresh).
        """
        now = time.time()
        cutoff = now - self._window
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        ttl = int(self._window) + 10
        redis_key = f"ratelimit:{key}"

        try:
            result = await self._redis.eval(
                _SLIDING_WINDOW_LUA,
                1,
                redis_key,
                str(now),
                str(cutoff),
                str(self._max),
                member,
                str(ttl),
            )
            return result == 1
        except Exception as exc:
            raise RateLimiterUnavailable(
                f"Redis unavailable during rate limit check for key={key!r}; "
                "refusing to fail open"
            ) from exc

    def _is_allowed_memory(self, key: str) -> bool:
        """In-memory sliding window check (fallback)."""
        now = time.monotonic()
        cutoff = now - self._window
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]
        if len(self._hits[key]) >= self._max:
            return False
        self._hits[key].append(now)
        return True
