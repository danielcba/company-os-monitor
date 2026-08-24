"""Tests for token blacklist: fail-closed and atomic refresh rotation (Phase 3).

Covers:
- Security-critical operations fail-closed when Redis is unavailable
- Non-critical operations fail-open when Redis is unavailable
- Atomic refresh token rotation (consume-once)
- Refresh token replay detection
- Sequential refresh
- Revoked token rejection
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


from libs.access.token_blacklist import (
    SecurityControlUnavailable,
    TokenBlacklist,
    _NoOpRedis,
)


class FakeRedis:
    """In-memory Redis mock for testing."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = value
        return True

    async def setnx(self, key: str, value: str, ex: int | None = None) -> bool:
        if key in self._store:
            return False
        self._store[key] = value
        return True

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def expire(self, key: str, time: int) -> bool:
        return True


class FailingRedis:
    """Redis that always raises (simulates Redis down)."""

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        from redis.exceptions import ConnectionError as RedisConnectionError
        raise RedisConnectionError("Redis unavailable")

    async def setnx(self, key: str, value: str, ex: int | None = None) -> bool:
        from redis.exceptions import ConnectionError as RedisConnectionError
        raise RedisConnectionError("Redis unavailable")

    async def exists(self, key: str) -> bool:
        from redis.exceptions import ConnectionError as RedisConnectionError
        raise RedisConnectionError("Redis unavailable")

    async def expire(self, key: str, time: int) -> bool:
        from redis.exceptions import ConnectionError as RedisConnectionError
        raise RedisConnectionError("Redis unavailable")


# --- is_revoked: fail-closed on Redis failure ---

async def test_is_revoked_fail_closed_on_redis_down():
    """Security-critical blacklist check raises when Redis is unavailable."""
    blacklist = TokenBlacklist(redis=FailingRedis())
    with pytest.raises(SecurityControlUnavailable):
        await blacklist.is_revoked(jti="some-token-jti")


async def test_is_revoked_returns_false_when_not_blacklisted():
    blacklist = TokenBlacklist(redis=FakeRedis())
    assert await blacklist.is_revoked(jti="not-revoked") is False


async def test_is_revoked_returns_true_when_blacklisted():
    redis = FakeRedis()
    blacklist = TokenBlacklist(redis=redis)
    await redis.set("jwt:blacklist:revoked-jti", "1", ex=3600)
    assert await blacklist.is_revoked(jti="revoked-jti") is True


async def test_is_revoked_empty_jti_returns_false():
    blacklist = TokenBlacklist(redis=FailingRedis())
    # Empty jti should short-circuit without hitting Redis.
    assert await blacklist.is_revoked(jti="") is False


# --- is_revoked_non_critical: fail-open on Redis failure ---

async def test_is_revoked_non_critical_fail_open_on_redis_down():
    """Non-critical check returns False when Redis is unavailable."""
    blacklist = TokenBlacklist(redis=FailingRedis())
    assert await blacklist.is_revoked_non_critical(jti="some-token") is False


async def test_is_revoked_non_critical_returns_true_when_blacklisted():
    redis = FakeRedis()
    blacklist = TokenBlacklist(redis=redis)
    await redis.set("jwt:blacklist:revoked-jti", "1", ex=3600)
    assert await blacklist.is_revoked_non_critical(jti="revoked-jti") is True


# --- consume_refresh_token: atomic consume-once ---

async def test_consume_refresh_token_first_use_succeeds():
    """First use of a refresh token succeeds."""
    blacklist = TokenBlacklist(redis=FakeRedis())
    result = await blacklist.consume_refresh_token(jti="refresh-123", expires_at=9999999999)
    assert result is True


async def test_consume_refresh_token_replay_detected():
    """Second use of the same refresh token is rejected."""
    blacklist = TokenBlacklist(redis=FakeRedis())
    first = await blacklist.consume_refresh_token(jti="refresh-123", expires_at=9999999999)
    assert first is True
    second = await blacklist.consume_refresh_token(jti="refresh-123", expires_at=9999999999)
    assert second is False


async def test_consume_refresh_token_different_jti_independent():
    """Different refresh tokens are consumed independently."""
    blacklist = TokenBlacklist(redis=FakeRedis())
    r1 = await blacklist.consume_refresh_token(jti="token-a", expires_at=9999999999)
    r2 = await blacklist.consume_refresh_token(jti="token-b", expires_at=9999999999)
    assert r1 is True
    assert r2 is True


async def test_consume_refresh_token_fail_closed_on_redis_down():
    """Refresh token consumption raises when Redis is unavailable."""
    blacklist = TokenBlacklist(redis=FailingRedis())
    with pytest.raises(SecurityControlUnavailable):
        await blacklist.consume_refresh_token(jti="refresh-xyz", expires_at=9999999999)


# --- revoke ---

async def test_revoke_sets_blacklist_key():
    redis = FakeRedis()
    blacklist = TokenBlacklist(redis=redis)
    await blacklist.revoke(jti="revoke-me", expires_at=9999999999)
    assert await redis.exists("jwt:blacklist:revoke-me")


# --- _NoOpRedis ---

async def test_noop_redis_does_not_raise():
    blacklist = TokenBlacklist(redis=_NoOpRedis())
    assert await blacklist.is_revoked(jti="test") is False
    assert await blacklist.is_revoked_non_critical(jti="test") is False
