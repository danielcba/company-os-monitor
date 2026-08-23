"""Redis-backed JWT token blacklist for revocation (external, ADR-0002).

Provides a distributed token blacklist using Redis sorted sets. When a token
is revoked (logout, refresh rotation, user deactivation), its ``jti`` claim
is added to the blacklist with a TTL matching the token's expiry.

The gateway checks the blacklist on every authentication attempt. If the jti
is found, the token is rejected even if the signature and expiry are valid.

Redis keys:
- ``jwt:blacklist:{jti}`` — SET with TTL (seconds) for O(1) lookup
- ``jwt:blacklist:idx`` — sorted set for range queries (optional, for admin)

Usage::

    from libs.access.token_blacklist import TokenBlacklist

    blacklist = TokenBlacklist(redis_url="redis://localhost:6379/1")
    await blacklist.revoke(jti="abc-123", expires_at=1700000000)
    is_revoked = await blacklist.is_revoked(jti="abc-123")
"""
import logging
from typing import Protocol

logger = logging.getLogger(__name__)

# Redis key prefix for blacklisted tokens.
_KEY_PREFIX = "jwt:blacklist:"
# Default TTL buffer: revoke tokens for at least this long even if expiry is near.
_MIN_REVOKE_TTL = 60  # seconds


class RedisClient(Protocol):
    """Minimal async Redis interface for the blacklist."""

    async def set(self, key: str, value: str, ex: int | None = None) -> bool: ...

    async def exists(self, key: str) -> bool: ...

    async def expire(self, key: str, time: int) -> bool: ...


class TokenBlacklist:
    """Distributed JWT blacklist backed by Redis.

    Each revoked token is stored as ``jwt:blacklist:{jti}`` with a TTL
    matching the token's remaining expiry (or ``_MIN_REVOKE_TTL`` if the
    token is near expiry).
    """

    def __init__(self, redis: RedisClient):
        self._redis = redis

    @classmethod
    def from_url(cls, redis_url: str = "redis://localhost:6379/1") -> "TokenBlacklist":
        """Create a blacklist from a Redis URL using the ``redis`` package."""
        try:
            from redis.asyncio import Redis

            redis = Redis.from_url(redis_url, decode_responses=True)
            return cls(redis=redis)
        except ImportError:
            logger.warning(
                "redis package not installed; token blacklist disabled "
                "(pip install redis)"
            )
            return cls(redis=_NoOpRedis())

    async def revoke(self, *, jti: str, expires_at: int) -> None:
        """Blacklist a token by its jti until its natural expiry.

        Args:
            jti: The unique JWT ID to blacklist.
            expires_at: Token expiry as epoch seconds (``exp`` claim).
        """
        import time

        now = int(time.time())
        ttl = max(expires_at - now, _MIN_REVOKE_TTL)
        key = f"{_KEY_PREFIX}{jti}"
        try:
            await self._redis.set(key, "1", ex=ttl)
            logger.info("token revoked: jti=%s ttl=%ds", jti, ttl)
        except Exception:
            logger.exception("failed to revoke token jti=%s", jti)

    async def is_revoked(self, *, jti: str) -> bool:
        """Check whether a token's jti has been blacklisted.

        Returns False if Redis is unavailable (fail-open for availability).
        """
        if not jti:
            return False
        key = f"{_KEY_PREFIX}{jti}"
        try:
            return bool(await self._redis.exists(key))
        except Exception:
            logger.warning("blacklist check failed for jti=%s; failing open", jti)
            return False


class _NoOpRedis:
    """Fallback when redis package is not installed; all ops are no-ops."""

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        return True

    async def exists(self, key: str) -> bool:
        return False

    async def expire(self, key: str, time: int) -> bool:
        return True
