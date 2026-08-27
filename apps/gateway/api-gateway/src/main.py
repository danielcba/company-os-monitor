"""API Gateway Entry Point - Cognitive Boundary enforcement (R3, external).

External non-canonical capability (ADR-0002): validates JWT authority and
routes pipeline access; it NEVER reimplements cognitive logic. Port
GATEWAY_HEALTH_PORT (8100).
"""
import asyncio
import logging
import os

from src.health import GatewayServer
from src.service import DEFAULT_SERVICE_HEALTH, GatewayService

logger = logging.getLogger(__name__)


def _build_service_health() -> dict[str, str]:
    """Service health map from env (override) or the canonical default ports."""
    override = os.getenv("GATEWAY_SERVICE_HEALTH")
    if not override:
        return dict(DEFAULT_SERVICE_HEALTH)
    mapping: dict[str, str] = {}
    for entry in override.split(","):
        if "=" in entry:
            service, url = entry.strip().split("=", 1)
            mapping[service.strip()] = url.strip()
    return mapping or dict(DEFAULT_SERVICE_HEALTH)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("GATEWAY_HEALTH_PORT", "8100"))
    redis_url = os.getenv("JWT_REDIS_URL", "redis://localhost:6379/1")

    from libs.access.security import JwtService
    from libs.access.token_blacklist import TokenBlacklist
    from libs.action.decision import DecisionStore
    from libs.action.report import ReportStore
    from libs.cognitive_core.summary import CognitiveSummaryStore
    from libs.memory.consolidation import ConsolidationStore
    from libs.memory.pattern_refinement import PatternRefinementStore
    from libs.shared.db import create_shared_engine

    from src.audit import AuditLogReadStore
    from src.cognitive_trace import CognitiveTraceStore
    from src.confidence import ConfidenceReadStore
    from src.decisions import DecisionReadStore
    from src.hypotheses import HypothesisReadStore
    from src.insights import InsightReadStore
    from src.observations import ObservationReadStore
    from src.patterns import PatternReadStore
    from src.recommendations import RecommendationReadStore

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    jwt = JwtService(
        algorithm=algorithm,
        secret_key=os.getenv("JWT_SECRET_KEY"),
        private_key=os.getenv("JWT_PRIVATE_KEY"),
        public_key=os.getenv("JWT_PUBLIC_KEY"),
        access_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")),
        refresh_expire_days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
    )

    # Create one shared async engine with production-ready pool settings
    engine = create_shared_engine(dsn)

    # Redis-backed JWT blacklist for token revocation
    blacklist = TokenBlacklist.from_url(redis_url)

    # READ routes read pipeline data directly (viewer+): decisions + reports + observations + audit + insights.
    decision_store = DecisionStore(dsn)
    report_store = ReportStore(dsn)
    observation_store = ObservationReadStore(engine=engine)
    audit_store = AuditLogReadStore(engine=engine)
    insight_store = InsightReadStore(engine=engine)
    summary_store = CognitiveSummaryStore(engine)

    # Detail stores for decision/recommendation desglose
    hypothesis_store = HypothesisReadStore(engine=engine)
    confidence_store = ConfidenceReadStore(engine=engine, hypothesis_store=hypothesis_store)
    recommendation_read_store = RecommendationReadStore(
        engine=engine, hypothesis_store=hypothesis_store, confidence_store=confidence_store
    )
    decision_read_store = DecisionReadStore(
        engine=engine, recommendation_store=recommendation_read_store, confidence_store=confidence_store
    )
    cognitive_trace_store = CognitiveTraceStore(engine=engine)

    # Memory (P7) Outcome Consolidation: read/compute over the canonical
    # Decision store (external capability, ADR-0002). No new entity/persistence.
    consolidation_store = ConsolidationStore(decision_store=decision_store)

    # Pattern Refinement (P7): read/compute over the canonical gateway read
    # stores (external capability, ADR-0002). The gateway boundary forbids
    # importing the reasoning/perception pipeline packages, so this capability
    # consumes the read contract (dict payloads) only — the traceability chain
    # Decision -> Recommendation -> Hypothesis -> Pattern feeds the signal.
    pattern_read_store = PatternReadStore(dsn)
    pattern_refinement_store = PatternRefinementStore(
        decision_store=decision_read_store,
        recommendation_store=recommendation_read_store,
        hypothesis_store=hypothesis_store,
        pattern_store=pattern_read_store,
    )

    await decision_store.verify_connection()
    await report_store.verify_connection()
    await observation_store.verify_connection()
    await audit_store.verify_connection()
    await insight_store.verify_connection()
    await hypothesis_store.verify_connection()
    await confidence_store.verify_connection()
    await recommendation_read_store.verify_connection()
    await decision_read_store.verify_connection()
    await cognitive_trace_store.verify_connection()
    await pattern_read_store.verify_connection()

    service = GatewayService(
        jwt,
        decision_store=decision_store,
        report_store=report_store,
        observation_store=observation_store,
        cognitive_summary_store=summary_store,
        audit_store=audit_store,
        insight_store=insight_store,
        decision_read_store=decision_read_store,
        recommendation_read_store=recommendation_read_store,
        cognitive_trace_store=cognitive_trace_store,
        consolidation_store=consolidation_store,
        pattern_refinement_store=pattern_refinement_store,
        service_health=_build_service_health(),
        dsn=dsn,
        blacklist=blacklist,
        confidence_store=confidence_store,
    )
    server = GatewayServer(service, jwt)

    await server.start(port)

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await server.stop()
        await engine.dispose()
        await decision_store.close()
        await report_store.close()
        await cognitive_trace_store.close()


if __name__ == "__main__":
    asyncio.run(main())
