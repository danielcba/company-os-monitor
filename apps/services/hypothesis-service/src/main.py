"""Hypothesis Service Entry Point - Hypothesis Generator (Reasoning/Predict).

The Reasoning Layer's Predict capability: reads each tenant's Anomalies,
Contexts and Patterns (knowledge, never raw observations) from Postgres,
instantiates the candidate explanations of the Hypothesis Template Library
(procedural memory) over the measured facts, and writes Candidate Hypotheses
into ``hypotheses`` (append-only, idempotent dedup). Hypotheses are always
tentative (``candidate``): the system never confirms or falsifies - future
evidence and calibrated Confidence (Sprint 8) decide.
"""
import asyncio
import logging
import os

from libs.perception.context import ContextStore
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore
from libs.reasoning.pattern import PatternStore
from libs.shared.graceful_shutdown import GracefulShutdown

from src.health import HealthServer
from src.service import HypothesisService

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("HYPOTHESIS_HEALTH_PORT", "8094"))
    cycle_seconds = float(os.getenv("HYPOTHESIS_CYCLE_SECONDS", "60"))

    anomaly_store = AnomalyStore(dsn)
    context_store = ContextStore(dsn)
    pattern_store = PatternStore(dsn)
    hypothesis_store = HypothesisStore(dsn)
    await anomaly_store.verify_connection()
    await context_store.verify_connection()
    await pattern_store.verify_connection()
    await hypothesis_store.verify_connection()

    service = HypothesisService(
        anomaly_store,
        context_store,
        pattern_store,
        hypothesis_store,
    )
    health = HealthServer(service)

    await health.start(port)

    shutdown = GracefulShutdown()
    shutdown.install()

    while not shutdown.should_exit.is_set():
        try:
            await service.run_generation_cycle()
        except Exception:
            logger.exception("Error in hypothesis generation cycle")
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())