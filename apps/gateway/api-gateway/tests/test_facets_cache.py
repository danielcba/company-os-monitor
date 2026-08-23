"""Unit tests for the in-memory facets cache with TTL."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "libs" / "shared"))

from facets_cache import FacetsCache


def test_cache_miss_returns_none():
    cache = FacetsCache(ttl_seconds=60)
    assert cache.get("nonexistent") is None


def test_cache_hit_returns_stored_value():
    cache = FacetsCache(ttl_seconds=60)
    cache.set("key-1", {"fact_types": ["cpu"]})
    result = cache.get("key-1")
    assert result == {"fact_types": ["cpu"]}


def test_cache_expires_after_ttl():
    cache = FacetsCache(ttl_seconds=0.01)
    cache.set("key-1", "value-1")
    assert cache.get("key-1") == "value-1"
    time.sleep(0.02)
    assert cache.get("key-1") is None


def test_overwrite_updates_value():
    cache = FacetsCache(ttl_seconds=60)
    cache.set("key-1", "first")
    cache.set("key-1", "second")
    assert cache.get("key-1") == "second"


def test_different_keys_are_independent():
    cache = FacetsCache(ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1
    assert cache.get("b") == 2
