"""Redis-backed JWT token blacklist for revocation (external, ADR-0002).

Provides a distributed token blacklist using Redis. When a token is revoked
(logout, refresh rotation, user deactivation), its ``jti`` claim is added to
the blacklist with a TTL matching the token's expiry.

The gateway checks the blacklist on every authentication attempt. If the jti
is found, the token is rejected even if the signature and expiry are valid.

Phase 3 (JWT/Token Security):
- Security-critical operations (refresh, logout, propose, commit, execute,
  authorization) now FAIL-CLOSED when Redis is unavailable.
- Non-critical operations (metrics, health, telemetry) remain fail-open.
- Atomic refresh token rotation using SET NX EX (consume-once).

Redis keys:
- ``jwt:blacklist:{jti}`` — SET with TTL (seconds) for O(1) lookup
- ``jwt:refresh:{jti}`` — SET NX EX for atomic consume-once rotation

Usage::

    from libs.access.token_blacklist import TokenBlacklist

    blacklist = TokenBlacklist(redis_url="redis://localhost:6379/1")
    await blacklist.revoke(jti="abc-123", expires_at=1700000000)
    is_revoked = await blacklist.is_revoked(jti="abc-123")
"""
import logging
import time
from typing import Protocol

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# Redis key prefix for blacklisted tokens.
_KEY_PREFIX = "jwt:blacklist:"
# Redis key prefix for refresh token consumption.
_REFRESH_PREFIX = "jwt:refresh:"
# Default TTL buffer: revoke tokens for at least this long even if expiry is near.
_MIN_REVOKE_TTL = 60  # seconds


class SecurityControlUnavailable(Exception):
    """Raised when a security control (Redis) is unavailable during a
    security-critical operation. The operation MUST NOT proceed."""

    @classmethod
    def redis_uninstalled(cls) -> "SecurityControlUnavailable":
        return cls(
            "Redis unavailable (package not installed); "
            "cannot perform security-critical operation"
        )

    @classmethod
    def check_failed(cls, jti: str) -> "SecurityControlUnavailable":
        return cls(
            f"Redis unavailable during security-critical blacklist check "
            f"for jti={jti!r}; refusing to fail open"
        )

    @classmethod
    def consume_failed(cls, jti: str) -> "SecurityControlUnavailable":
        return cls(
            f"Redis unavailable during refresh token consumption "
            f"for jti={jti!r}; refusing to fail open"
        )


class RedisClient(Protocol):
    """Minimal async Redis interface for the blacklist."""

    async def set(self, key: str, value: str, ex: int | None = None) -> bool: ...

    async def setnx(self, key: str, value: str, ex: int | None = None) -> bool: ...

    async def exists(self, key: str) -> bool: ...

    async def expire(self, key: str, time: int) -> bool: ...


class TokenBlacklist:
    """Distributed JWT blacklist backed by Redis.

    Each revoked token is stored as ``jwt:blacklist:{jti}`` with a TTL
    matching the token's remaining expiry (or ``_MIN_REVOKE_TTL`` if the
    token is near expiry).

    Phase 3: Security-critical operations raise ``SecurityControlUnavailable``
    when Redis is down (fail-closed). Non-critical checks (health, metrics)
    can use ``is_revoked_non_critical`` for fail-open behavior.
    """

    def __init__(self, redis: RedisClient):
        self._redis = redis

    @classmethod
    def from_url(cls, redis_url: str = "redis://localhost:6379/1") -> "TokenBlacklist":
        """Create a blacklist from a Redis URL using the ``redis`` package."""
        try:
            from redis.asyncio import Redis  # noqa: PLC0415 - lazy import by design

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
        now = int(time.time())
        ttl = max(expires_at - now, _MIN_REVOKE_TTL)
        key = f"{_KEY_PREFIX}{jti}"
        try:
            await self._redis.set(key, "1", ex=ttl)
            logger.info("token revoked: jti=%s ttl=%ds", jti, ttl)
        except Exception:
            logger.exception("failed to revoke token jti=%s", jti)

    async def is_revoked(self, *, jti: str) -> bool:
        """Check whether a token's jti has been blacklisted (SECURITY-CRITICAL).

        FAIL-CLOSED: raises SecurityControlUnavailable if Redis is down.
        Used for auth, refresh, logout, propose, commit, execute operations.
        """
        if not jti:
            return False
        key = f"{_KEY_PREFIX}{jti}"
        try:
            return bool(await self._redis.exists(key))
        except Exception as exc:
            raise SecurityControlUnavailable.check_failed(jti) from exc

    async def is_revoked_non_critical(self, *, jti: str) -> bool:
        """Check blacklist with fail-open behavior (NON-CRITICAL only).

        Used for metrics, health checks, telemetry — operations where
        availability is more critical than perfect revocation checking.
        """
        if not jti:
            return False
        key = f"{_KEY_PREFIX}{jti}"
        try:
            return bool(await self._redis.exists(key))
        except RedisError:
            logger.warning("blacklist check failed for jti=%s; failing open (non-critical)", jti)
            return False

    async def consume_refresh_token(self, *, jti: str, expires_at: int) -> bool:
        """Atomic consume-once for refresh token rotation (Phase 3).

        Uses Redis SET NX EX to atomically check-and-consume a refresh token.
        The first request succeeds (sets the key); concurrent/duplicate requests
        detect the key already exists and reject.

        Returns:
            True if the refresh token was successfully consumed (first use).
            False if the token was already consumed (replay attempt).

        Raises:
            SecurityControlUnavailable: If Redis is unavailable.
        """
        now = int(time.time())
        ttl = max(expires_at - now, _MIN_REVOKE_TTL)
        key = f"{_REFRESH_PREFIX}{jti}"
        try:
            # SET NX: only set if not exists. Returns True if set, False if already exists.
            consumed = await self._redis.setnx(key, "1", ex=ttl)
            if not consumed:
                logger.warning("refresh token replay detected: jti=%s", jti)
            return bool(consumed)
        except Exception as exc:
            raise SecurityControlUnavailable.consume_failed(jti) from exc


class _NoOpRedis:
    """Fallback when redis package is not installed.

    Security-critical operations (revoke, consume) raise
    SecurityControlUnavailable to prevent fail-open behavior.
    Non-critical operations (exists) return safe defaults.
    """

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        raise SecurityControlUnavailable.redis_uninstalled()

    async def setnx(self, key: str, value: str, ex: int | None = None) -> bool:
        raise SecurityControlUnavailable.redis_uninstalled()

    async def exists(self, key: str) -> bool:
        return False

    async def expire(self, key: str, time: int) -> bool:
        return True
