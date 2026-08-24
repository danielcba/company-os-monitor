"""Unit tests for the atomic sliding window rate limiter (Phase 4)."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "apps" / "services" / "user-service" / "src"))

from ratelimit import RateLimiter


async def test_first_request_allowed():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert await limiter.is_allowed("client-1") is True


async def test_allows_up_to_max_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert await limiter.is_allowed("client-1") is True
    assert await limiter.is_allowed("client-1") is True
    assert await limiter.is_allowed("client-1") is True


async def test_blocks_after_max_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        await limiter.is_allowed("client-1")
    assert await limiter.is_allowed("client-1") is False


async def test_resets_after_window_expires():
    limiter = RateLimiter(max_requests=2, window_seconds=0.01)
    await limiter.is_allowed("client-1")
    await limiter.is_allowed("client-1")
    assert await limiter.is_allowed("client-1") is False
    time.sleep(0.02)
    assert await limiter.is_allowed("client-1") is True


async def test_different_keys_are_independent():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert await limiter.is_allowed("client-A") is True
    assert await limiter.is_allowed("client-B") is True
    assert await limiter.is_allowed("client-A") is False
    assert await limiter.is_allowed("client-B") is False


async def test_expired_hits_are_purged():
    limiter = RateLimiter(max_requests=2, window_seconds=0.01)
    await limiter.is_allowed("client-1")
    time.sleep(0.02)
    await limiter.is_allowed("client-1")
    assert len(limiter._hits["client-1"]) == 1
