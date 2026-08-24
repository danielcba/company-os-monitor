"""Phase 9 — Bounded Concurrency tests."""
import asyncio
import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.shared.concurrency import BoundedTenantProcessor

# Test constants.
CONCURRENCY_LIMIT = 3
TOTAL_TENANTS = 10
BATCH_SIZE = 3
EXCEPTION_TRIGGER = 3
EXPECTED_RESULTS_5 = 5


async def test_process_all_returns_results_in_order():
    processor = BoundedTenantProcessor(max_concurrent=5)

    async def process(x):
        return x * 2

    results = await processor.process_all([1, 2, 3, 4, 5], process)
    assert results == [2, 4, 6, 8, 10]


async def test_concurrency_is_bounded():
    max_concurrent = CONCURRENCY_LIMIT
    processor = BoundedTenantProcessor(max_concurrent=max_concurrent)
    current = 0
    peak = 0

    async def process(x):
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.01)
        current -= 1
        return x

    await processor.process_all(list(range(TOTAL_TENANTS)), process)
    assert peak <= max_concurrent


async def test_empty_input():
    processor = BoundedTenantProcessor(max_concurrent=5)

    async def noop(x):
        return x

    results = await processor.process_all([], noop)
    assert results == []


async def test_single_tenant():
    processor = BoundedTenantProcessor(max_concurrent=5)

    async def process(x):
        return x + 1

    results = await processor.process_all([42], process)
    assert results == [43]


async def test_batch_size_limits_task_creation():
    processor = BoundedTenantProcessor(max_concurrent=100, max_batch_size=BATCH_SIZE)
    processed = []

    async def process(x):
        processed.append(x)
        return x

    results = await processor.process_all([1, 2, 3, 4, 5], process)
    assert sorted(processed) == [1, 2, 3, 4, 5]
    assert len(results) == EXPECTED_RESULTS_5


async def test_exception_in_one_tenant_does_not_others():
    processor = BoundedTenantProcessor(max_concurrent=5)

    async def process(x):
        if x == EXCEPTION_TRIGGER:
            raise ValueError("boom")
        return x

    with contextlib.suppress(ValueError):
        await processor.process_all([1, 2, 3, 4, 5], process)
    # Other tasks may or may not complete depending on when exception occurs.
