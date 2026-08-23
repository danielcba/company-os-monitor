"""Distributed sliding window rate limiter backed by Redis sorted sets.

Uses Redis ZRANGEBYSCORE for O(log N) sliding window checks. Falls back to
in-memory when Redis is unavailable (fail-open for availability).

Redis key pattern: ``ratelimit:{key}``
Sorted set members: ``{timestamp}:{random}`` (unique per request)
Score: request timestamp (epoch seconds, float)

Usage::

    from src.ratelimit import RateLimiter

    limiter = RateLimiter.from_url("redis://localhost:6379/1")
    if not limiter.is_allowed(f"login:{client_ip}"):
        return 429
"""
import os
import time
import uuid
from collections import defaultdict
from typing import Protocol


class RedisClient(Protocol):
    """Minimal async Redis interface for the rate limiter."""

    async def zremrangebyscore(self, key: str, min: float, max: float) -> int: ...

    async def zcard(self, key: str) -> int: ...

    async def zadd(self, key: str, mapping: dict[str, float]) -> int: ...

    async def expire(self, key: str, time: int) -> bool: ...


class RateLimiter:
    """Sliding window rate limiter keyed by IP or identifier.

    Supports both Redis-backed (distributed) and in-memory (standalone) modes.
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

    def is_allowed(self, key: str) -> bool:
        """Return True if the request is allowed, False if rate-limited.

        Uses Redis sorted sets when available, falls back to in-memory.
        """
        if self._redis is not None:
            return self._is_allowed_redis(key)
        return self._is_allowed_memory(key)

    def _is_allowed_redis(self, key: str) -> bool:
        """Redis-backed sliding window check (synchronous wrapper)."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, self._is_allowed_redis_async(key)
                    )
                    return future.result(timeout=5)
            else:
                return loop.run_until_complete(self._is_allowed_redis_async(key))
        except Exception:
            # Fail-open: if Redis is unavailable, allow the request.
            return self._is_allowed_memory(key)

    async def _is_allowed_redis_async(self, key: str) -> bool:
        """Async Redis-backed sliding window check."""
        now = time.time()
        cutoff = now - self._window
        redis_key = f"ratelimit:{key}"

        # Remove expired entries.
        await self._redis.zremrangebyscore(redis_key, "-inf", cutoff)

        # Count current window requests.
        count = await self._redis.zcard(redis_key)

        if count >= self._max:
            return False

        # Add current request with unique member (timestamp + UUID).
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        await self._redis.zadd(redis_key, {member: now})

        # Set TTL on the key (window + buffer for cleanup).
        await self._redis.expire(redis_key, int(self._window) + 10)

        return True

    def _is_allowed_memory(self, key: str) -> bool:
        """In-memory sliding window check (fallback)."""
        now = time.monotonic()
        cutoff = now - self._window
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]
        if len(self._hits[key]) >= self._max:
            return False
        self._hits[key].append(now)
        return True
