"""Decision Service Entry Point - Decision Committer (Action/Commit).

The Action Layer's Commit capability: reads each tenant's proposed
Recommendations (offers, advisory) together with the calibrated Confidence bound
to each (R4), resolves the explicit Decision Policy of the domain (procedural
memory) and writes committed Decisions into ``decisions`` (append-only,
idempotent dedup). It NEVER writes to previous artifacts (P1), never reads the
observation bus, never calibrates confidence and never forms recommendations
(R1: exactly one capability) and never executes real-world actions or triggers
alerts (P6: the Decision is recorded with its falsifiable expected outcomes;
execution and authorization belong to future phases).
"""
import asyncio
import logging
import os

from libs.action.decision import DecisionStore
from libs.action.recommendation import RecommendationStore
from libs.learning.confidence import ConfidenceStore
from libs.shared.graceful_shutdown import GracefulShutdown

from src.health import HealthServer
from src.service import DecisionService

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("DECISION_HEALTH_PORT", "8097"))
    cycle_seconds = float(os.getenv("DECISION_CYCLE_SECONDS", "60"))
    min_confidence_for_commit = float(os.getenv("DECISION_MIN_CONFIDENCE", "0.75"))
    min_confidence_irreversible = float(
        os.getenv("DECISION_MIN_CONFIDENCE_IRREVERSIBLE", "0.9")
    )

    recommendation_store = RecommendationStore(dsn)
    confidence_store = ConfidenceStore(dsn)
    decision_store = DecisionStore(dsn)
    await recommendation_store.verify_connection()
    await confidence_store.verify_connection()
    await decision_store.verify_connection()

    service = DecisionService(
        recommendation_store,
        confidence_store,
        decision_store,
        min_confidence_for_commit=min_confidence_for_commit,
        min_confidence_irreversible=min_confidence_irreversible,
    )
    health = HealthServer(service)

    await health.start(port)

    shutdown = GracefulShutdown()
    shutdown.install()

    while not shutdown.should_exit.is_set():
        try:
            await service.run_decision_cycle()
        except Exception:
            logger.exception("Error in decision cycle")
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())