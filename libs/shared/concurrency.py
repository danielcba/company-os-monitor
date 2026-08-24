"""Bounded concurrency utilities for multi-tenant cognitive processing.

Phase 9: Prevent saturation when processing multiple tenants concurrently.
Instead of `asyncio.gather(all_tenants)` (unbounded), use a semaphore to
limit concurrent operations.

Usage::

    from libs.shared.concurrency import BoundedTenantProcessor

    processor = BoundedTenantProcessor(max_concurrent=10)
    results = await processor.process_all(tenant_ids, process_fn)

Configuration via environment variables:
- MAX_CONCURRENT_TENANTS: Max concurrent tenant operations (default: 10)
- MAX_BATCH_SIZE: Max tenants per batch (default: 100)
"""
import asyncio
import os
from typing import Any, Awaitable, Callable

# Default concurrency limits.
DEFAULT_MAX_CONCURRENT_TENANTS = 10
DEFAULT_MAX_BATCH_SIZE = 100


class BoundedTenantProcessor:
    """Process tenants with bounded concurrency to prevent saturation.

    The parallelization is technical, not cognitive — it doesn't alter the
    semantic meaning of the cognitive pipeline, only how many tenants are
    processed concurrently.

    Usage::

        processor = BoundedTenantProcessor(max_concurrent=10)

        async def process_tenant(tenant_id: UUID) -> Result:
            ...

        results = await processor.process_all(tenant_ids, process_tenant)
    """

    def __init__(
        self,
        max_concurrent: int | None = None,
        max_batch_size: int | None = None,
    ):
        if max_concurrent is None:
            max_concurrent = int(
                os.getenv("MAX_CONCURRENT_TENANTS", str(DEFAULT_MAX_CONCURRENT_TENANTS))
            )
        if max_batch_size is None:
            max_batch_size = int(
                os.getenv("MAX_BATCH_SIZE", str(DEFAULT_MAX_BATCH_SIZE))
            )
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_batch_size = max_batch_size

    async def process_all(
        self,
        tenant_ids: list[Any],
        process_fn: Callable[[Any], Awaitable[Any]],
    ) -> list[Any]:
        """Process all tenants with bounded concurrency.

        Splits tenants into batches of ``max_batch_size`` and processes each
        batch with at most ``max_concurrent`` simultaneous operations.

        Returns results in the same order as input tenant_ids.
        """
        results: list[Any] = [None] * len(tenant_ids)

        async def _bounded_process(idx: int, tenant_id: Any) -> None:
            async with self._semaphore:
                results[idx] = await process_fn(tenant_id)

        # Process in batches to avoid unbounded task creation.
        for batch_start in range(0, len(tenant_ids), self._max_batch_size):
            batch_end = min(batch_start + self._max_batch_size, len(tenant_ids))
            batch = tenant_ids[batch_start:batch_end]
            tasks = [
                _bounded_process(batch_start + i, tid)
                for i, tid in enumerate(batch)
            ]
            await asyncio.gather(*tasks)

        return results
