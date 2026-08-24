"""05 - Refresh Concurrent: 50 concurrent refreshes with same token.

Verifies atomic consume-once under concurrency.
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from libs.access.token_blacklist import TokenBlacklist


class FakeRedis:
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


async def test_50_concurrent_refresh_exactly_one_succeeds():
    """50 concurrent refresh requests with the same token: exactly 1 must succeed."""
    redis = FakeRedis()
    blacklist = TokenBlacklist(redis=redis)
    jti = str(uuid.uuid4())

    async def _consume():
        return await blacklist.consume_refresh_token(jti=jti, expires_at=9999999999)

    TOTAL_CONCURRENT = 50
    results = await asyncio.gather(*[_consume() for _ in range(TOTAL_CONCURRENT)])
    successes = sum(1 for r in results if r is True)
    failures = sum(1 for r in results if r is False)
    assert successes == 1, f"Expected exactly 1 success, got {successes}"
    expected_failures = TOTAL_CONCURRENT - 1
    assert failures == expected_failures, (
        f"Expected {expected_failures} failures, got {failures}"
    )
