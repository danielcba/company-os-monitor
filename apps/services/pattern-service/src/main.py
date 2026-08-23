"""Pattern Service Entry Point - Pattern Detector (Context -> Pattern).

The Reasoning Layer's Generalize capability: reads the tenant Context stream
(knowledge, never raw observations) from Postgres, measures the support of the
declarative Pattern Library over it, and writes Candidate Patterns into
``patterns`` (append-only, idempotent dedup).
"""
import asyncio
import logging
import os

from libs.perception.context import ContextStore
from libs.reasoning.pattern import PatternStore
from libs.shared.graceful_shutdown import GracefulShutdown

from src.health import HealthServer
from src.service import PatternService

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
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

    shutdown = GracefulShutdown()
    shutdown.install()

    while not shutdown.should_exit.is_set():
        try:
            await service.run_detection_cycle()
        except Exception:
            logger.exception("Error in detection cycle")
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())
