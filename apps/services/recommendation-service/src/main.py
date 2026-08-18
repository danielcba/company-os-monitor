"""Recommendation Service Entry Point - Recommendation Formulator (Action/Propose).

The Action Layer's Propose capability: reads each tenant's candidate Hypotheses
(understanding), their calibrated Confidence (Sprint 8) and their Active
Contexts from Postgres, resolves the explicit Action Space (procedural memory)
and writes proposed Recommendations into ``recommendations`` (append-only,
idempotent dedup). It NEVER writes to previous artifacts (P1), never reads the
observation bus, never calibrates confidence (R1: exactly one capability) and
never executes actions or triggers alerts (P6: a Recommendation is advisory and
reversible - the Decision layer, Sprint 10, is where commitment lives).
"""
import asyncio
import os

from libs.action.recommendation import RecommendationStore
from libs.learning.confidence import ConfidenceStore
from libs.perception.context import ContextStore
from libs.procedural_memory.action_space import (
    ACTION_SPACE_LIBRARY,
    filter_action_space,
)
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore

from src.health import HealthServer
from src.service import RecommendationService


def load_action_space() -> tuple:
    """The explicit Action Space, optionally restricted by deployment flag.

    ``ACTION_SPACE_DOMAINS`` is a comma-separated list of enabled domains
    (default empty = all catalog domains enabled). The Formulator may only
    choose within the spaces that remain enabled.
    """
    raw = os.getenv("ACTION_SPACE_DOMAINS", "")
    enabled = frozenset(domain.strip() for domain in raw.split(",") if domain.strip())
    return filter_action_space(ACTION_SPACE_LIBRARY, enabled)


async def main():
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("RECOMMENDATION_HEALTH_PORT", "8096"))
    cycle_seconds = float(os.getenv("RECOMMENDATION_CYCLE_SECONDS", "60"))

    hypothesis_store = HypothesisStore(dsn)
    anomaly_store = AnomalyStore(dsn)
    context_store = ContextStore(dsn)
    confidence_store = ConfidenceStore(dsn)
    recommendation_store = RecommendationStore(dsn)
    await hypothesis_store.verify_connection()
    await anomaly_store.verify_connection()
    await context_store.verify_connection()
    await confidence_store.verify_connection()
    await recommendation_store.verify_connection()

    service = RecommendationService(
        hypothesis_store,
        anomaly_store,
        context_store,
        confidence_store,
        recommendation_store,
        action_space=load_action_space(),
    )
    health = HealthServer(service)

    await health.start(port)

    while True:
        await service.run_recommendation_cycle()
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())