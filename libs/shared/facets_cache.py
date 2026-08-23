"""Simple in-memory cache with TTL for facets."""
import os
import time
from typing import Any


class FacetsCache:
    """In-memory TTL cache keyed by tenant + concept."""

    def __init__(self, ttl_seconds: int | None = None):
        self._ttl = ttl_seconds or int(os.getenv("FACETS_CACHE_TTL", "60"))
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.monotonic() - ts < self._ttl:
                return data
            del self._cache[key]
        return None

    def set(self, key: str, data: Any) -> None:
        self._cache[key] = (time.monotonic(), data)
