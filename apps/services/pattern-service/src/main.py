"""Pattern Service Entry Point - Pattern Detector (Context -> Pattern).

The Reasoning Layer's Generalize capability: reads the tenant Context stream
(knowledge, never raw observations) from Postgres, measures the support of the
declarative Pattern Library over it, and writes Candidate Patterns into
``patterns`` (append-only, idempotent dedup).
"""
import asyncio
import os

from libs.perception.context import ContextStore
from libs.reasoning.pattern import PatternStore

from src.health import HealthServer
from src.service import PatternService


async def main():
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("PATTERN_HEALTH_PORT", "8092"))
    cycle_seconds = float(os.getenv("DETECTION_CYCLE_SECONDS", "60"))
    window_days = float(os.getenv("DETECTION_WINDOW_DAYS", "28"))

    context_store = ContextStore(dsn)
    pattern_store = PatternStore(dsn)
    await context_store.verify_connection()
    await pattern_store.verify_connection()

    service = PatternService(
        context_store,
        pattern_store,
        window_days=window_days,
    )
    health = HealthServer(service)

    await health.start(port)

    while True:
        await service.run_detection_cycle()
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())
