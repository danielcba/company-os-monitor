"""Insight Service Entry Point - Insight Generator (Reasoning/Restructure).

The Reasoning Layer's Restructure capability: reads each tenant's Hypotheses
and their Active Contexts (knowledge, never raw observations) from Postgres,
applies the declarative Insight Rules (procedural memory) that detect a
competitive frame, and writes Insights into ``insights`` (append-only,
idempotent dedup, fully immutable). Insight "cannot be forced or scheduled":
the service only restructures when the declared rule condition is met - it
never invents facts, never judges and never asserts causation; it journals the
transformation (prior understanding + new organization + mental model update).
"""
import asyncio
import logging
import os

from libs.perception.context import ContextStore
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore
from libs.reasoning.insight import InsightStore
from libs.shared.graceful_shutdown import GracefulShutdown

from src.health import HealthServer
from src.service import InsightService

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("INSIGHT_HEALTH_PORT", "8101"))
    cycle_seconds = float(os.getenv("INSIGHT_CYCLE_SECONDS", "60"))

    hypothesis_store = HypothesisStore(dsn)
    anomaly_store = AnomalyStore(dsn)
    context_store = ContextStore(dsn)
    insight_store = InsightStore(dsn)
    await hypothesis_store.verify_connection()
    await anomaly_store.verify_connection()
    await context_store.verify_connection()
    await insight_store.verify_connection()

    service = InsightService(
        hypothesis_store,
        anomaly_store,
        context_store,
        insight_store,
    )
    health = HealthServer(service)

    await health.start(port)

    shutdown = GracefulShutdown()
    shutdown.install()

    while not shutdown.should_exit.is_set():
        try:
            await service.run_restructure_cycle()
        except Exception:
            logger.exception("Error in insight restructure cycle")
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())