"""Unit tests for the in-memory sliding window rate limiter."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "apps" / "services" / "user-service" / "src"))

from ratelimit import RateLimiter


def test_first_request_allowed():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.is_allowed("client-1") is True


def test_allows_up_to_max_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.is_allowed("client-1") is True
    assert limiter.is_allowed("client-1") is True
    assert limiter.is_allowed("client-1") is True


def test_blocks_after_max_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        limiter.is_allowed("client-1")
    assert limiter.is_allowed("client-1") is False


def test_resets_after_window_expires():
    limiter = RateLimiter(max_requests=2, window_seconds=0.01)
    limiter.is_allowed("client-1")
    limiter.is_allowed("client-1")
    assert limiter.is_allowed("client-1") is False
    time.sleep(0.02)
    assert limiter.is_allowed("client-1") is True


def test_different_keys_are_independent():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.is_allowed("client-A") is True
    assert limiter.is_allowed("client-B") is True
    assert limiter.is_allowed("client-A") is False
    assert limiter.is_allowed("client-B") is False


def test_expired_hits_are_purged():
    limiter = RateLimiter(max_requests=2, window_seconds=0.01)
    limiter.is_allowed("client-1")
    time.sleep(0.02)
    limiter.is_allowed("client-1")
    assert len(limiter._hits["client-1"]) == 1
