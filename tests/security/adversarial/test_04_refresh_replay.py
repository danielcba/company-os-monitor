"""04 - Refresh Replay: same refresh token must succeed exactly once.

Enforces: consume-once atomicity via Redis SET NX EX.
"""
import asyncio
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from libs.access.token_blacklist import SecurityControlUnavailable, TokenBlacklist


class FakeRedis:
    """In-memory Redis mock that simulates SET NX EX atomically."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def set(self, key, value, ex=None):
        self._store[key] = value
        return True

    async def setnx(self, key, value, ex=None):
        if key in self._store:
            return False
        self._store[key] = value
        return True

    async def exists(self, key):
        return key in self._store

    async def expire(self, key, time):
        return True


async def test_consume_first_use_succeeds():
    """First use of a refresh token must succeed."""
    redis = FakeRedis()
    blacklist = TokenBlacklist(redis=redis)
    jti = str(uuid.uuid4())

    result = await blacklist.consume_refresh_token(jti=jti, expires_at=9999999999)
    assert result is True


async def test_consume_replay_detected():
    """Second use of the same refresh token must be rejected."""
    redis = FakeRedis()
    blacklist = TokenBlacklist(redis=redis)
    jti = str(uuid.uuid4())

    first = await blacklist.consume_refresh_token(jti=jti, expires_at=9999999999)
    assert first is True
    second = await blacklist.consume_refresh_token(jti=jti, expires_at=9999999999)
    assert second is False


async def test_concurrent_replay_exactly_one_succeeds():
    """N concurrent requests with the same token: exactly 1 must succeed."""
    redis = FakeRedis()
    blacklist = TokenBlacklist(redis=redis)
    jti = str(uuid.uuid4())

    async def _consume():
        return await blacklist.consume_refresh_token(jti=jti, expires_at=9999999999)

    N = 50
    results = await asyncio.gather(*[_consume() for _ in range(N)])
    successes = sum(1 for r in results if r is True)
    assert successes == 1, f"Expected exactly 1 success, got {successes}"


async def test_different_jti_tokens_independent():
    """Different JTIs must not interfere with each other."""
    redis = FakeRedis()
    blacklist = TokenBlacklist(redis=redis)
    jti_a = str(uuid.uuid4())
    jti_b = str(uuid.uuid4())

    assert await blacklist.consume_refresh_token(jti=jti_a, expires_at=9999999999) is True
    assert await blacklist.consume_refresh_token(jti=jti_b, expires_at=9999999999) is True
    # Both are now consumed
    assert await blacklist.consume_refresh_token(jti=jti_a, expires_at=9999999999) is False
    assert await blacklist.consume_refresh_token(jti=jti_b, expires_at=9999999999) is False


async def test_consume_fail_closed_on_redis_down():
    """consume_refresh_token must raise when Redis is unavailable."""
    from libs.access.token_blacklist import _NoOpRedis

    blacklist = TokenBlacklist(redis=_NoOpRedis())
    with pytest.raises(SecurityControlUnavailable):
        await blacklist.consume_refresh_token(
            jti=str(uuid.uuid4()), expires_at=9999999999
        )
