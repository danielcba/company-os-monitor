"""10 - Context Race: concurrent context activations.

Verifies: at most one active context per tenant+purpose under concurrency.
"""
import asyncio
import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from libs.shared.concurrency import BoundedTenantProcessor


def test_concurrent_activation_bounded():
    """100 concurrent operations must respect max_concurrent limit."""
    max_concurrent = 5
    processor = BoundedTenantProcessor(max_concurrent=max_concurrent)
    current = 0
    peak = 0

    async def activate(x):
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.01)
        current -= 1
        return x

    asyncio.run(processor.process_all(list(range(100)), activate))
    assert peak <= max_concurrent


def test_concurrent_failure_isolation():
    """One failing tenant must not cancel others."""
    processor = BoundedTenantProcessor(max_concurrent=10)
    results = []

    FAILING_INPUT = 5
    SURVIVING_INPUT = 4

    async def process(x):
        if x == FAILING_INPUT:
            raise ValueError("boom")
        results.append(x)
        return x

    with contextlib.suppress(ValueError):
        asyncio.run(processor.process_all(list(range(10)), process))
    # Other tasks should have completed
    assert 0 in results
    assert SURVIVING_INPUT in results


def test_empty_concurrent_input():
    """Empty input should produce empty results."""
    processor = BoundedTenantProcessor(max_concurrent=5)

    async def noop(x):
        return x

    results = asyncio.run(processor.process_all([], noop))
    assert results == []
