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

    from libs.access.security import JwtService, MachineJwtService
    from libs.access.token_blacklist import TokenBlacklist
    from libs.action.decision import DecisionStore
    from libs.action.report import ReportStore
    from libs.memory.cognitive_timeline import CognitiveTimelineStore
    from libs.memory.consolidation import ConsolidationStore
    from libs.memory.context_revision import ContextRevisionStore
    from libs.memory.insight_transformation import InsightTransformationStore
    from libs.memory.learning_loop import LearningLoopStore
    from libs.memory.memory_ledger import MemoryStore
    from libs.memory.pattern_refinement import PatternRefinementStore
    from libs.shared.db import create_shared_engine

    from src.anomalies import AnomalyReadStore
    from src.audit import AuditLogReadStore
    from src.cognitive_trace import CognitiveTraceStore
    from src.confidence import ConfidenceReadStore
    from src.contexts import ContextReadStore
    from src.decisions import DecisionReadStore
    from src.evidence import EvidenceReadStore
    from src.hypotheses import HypothesisReadStore
    from src.insights import InsightReadStore
    from src.observations import ObservationReadStore
    from src.patterns import PatternReadStore
    from src.recommendations import RecommendationReadStore
    from src.summary import CognitiveSummaryStore

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    jwt = JwtService(
        algorithm=algorithm,
        secret_key=os.getenv("JWT_SECRET_KEY"),
        private_key=os.getenv("JWT_PRIVATE_KEY"),
        public_key=os.getenv("JWT_PUBLIC_KEY"),
        access_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")),
        refresh_expire_days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
    )

    # Machine JWT — RS256 with kid-based key rotation (ADR-0005 §1, H5)
    def _load_machine_keys() -> dict[str, tuple[str, str]]:
        """Load MACHINE_JWT_PRIVATE_KEY_<kid> + MACHINE_JWT_PUBLIC_KEY_<kid> from env."""
        active_kid = os.getenv("MACHINE_JWT_ACTIVE_KID", "")
        keys: dict[str, tuple[str, str]] = {}
        prefix = "MACHINE_JWT_PRIVATE_KEY_"
        for env_key, env_val in os.environ.items():
            if env_key.startswith(prefix):
                kid = env_key[len(prefix):]
                pub_key = os.getenv(f"MACHINE_JWT_PUBLIC_KEY_{kid}", "")
                if pub_key:
                    keys[kid] = (env_val, pub_key)
        return keys, active_kid

    machine_keys, machine_active_kid = _load_machine_keys()
    if machine_keys and machine_active_kid:
        machine_jwt = MachineJwtService(
            key_set=machine_keys,
            active_kid=machine_active_kid,
            access_expire_seconds=int(os.getenv("MACHINE_JWT_ACCESS_EXPIRE_SECONDS", "60")),
            refresh_expire_hours=int(os.getenv("MACHINE_JWT_REFRESH_EXPIRE_HOURS", "24")),
        )
    else:
        # Dev fallback: generate ephemeral RS256 key pair for local testing
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        _priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _priv_pem = _priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        _pub_pem = _priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        machine_jwt = MachineJwtService(
            key_set={"dev-key": (_priv_pem, _pub_pem)},
            active_kid="dev-key",
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

    # Context Revision (P7 + P2): read/compute over the canonical gateway read
    # stores (external capability, ADR-0002). The gateway boundary forbids
    # importing the reasoning/perception pipeline packages, so this capability
    # consumes the read contract (dict payloads) only — the traceability chain
    # Decision -> Recommendation -> Hypothesis -> Pattern -> Context feeds the
    # signal, and competing models are surfaced (never auto-activated, P2).
    context_read_store = ContextReadStore(dsn)
    context_revision_store = ContextRevisionStore(
        decision_store=decision_read_store,
        recommendation_store=recommendation_read_store,
        hypothesis_store=hypothesis_store,
        pattern_store=pattern_read_store,
        context_store=context_read_store,
    )

    # Cognitive Timeline (Investigation): read/compute reconstruction of the
    # tenant's chronological cognitive events from the canonical read stores
    # (external capability, ADR-0002). Never persists (P1); derived on demand.
    evidence_store = EvidenceReadStore(dsn)
    anomaly_store = AnomalyReadStore(dsn)
    timeline_store = CognitiveTimelineStore(
        observation_store=observation_store,
        evidence_store=evidence_store,
        context_store=context_read_store,
        pattern_store=pattern_read_store,
        anomaly_store=anomaly_store,
        hypothesis_store=hypothesis_store,
        insight_store=insight_store,
        recommendation_store=recommendation_read_store,
        decision_store=decision_read_store,
        report_store=report_store,
        confidence_store=confidence_store,
        audit_store=audit_store,
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
    await context_read_store.verify_connection()
    await timeline_store.verify_connection()

    # Insight Transformation journaling (R6): read/compute over the canonical
    # gateway read stores (external capability, ADR-0002). The gateway boundary
    # forbids importing the reasoning/perception pipeline packages, so this
    # capability consumes the read contract (dict payloads) only — it surfaces
    # each Insight's prior -> updated mental-model transformation and (with the
    # Decision/Recommendation readers) attributes outcome verdicts back to the
    # Insight that informed the Recommendation.
    insight_transformation_store = InsightTransformationStore(
        insight_store=insight_store,
        decision_store=decision_read_store,
        recommendation_store=recommendation_read_store,
    )

    # Learning Memory ledger (P7 persistence, authorized 2026-08-27): a NEW
    # append-only entity. Distinct from the read/compute capabilities above —
    # this is the only one that writes (idempotent POST). Canonical entities
    # are never mutated (P1).
    memory_store = MemoryStore(dsn)
    await memory_store.verify_connection()

    # Learning Loop (P7): automatic feedback Decision outcomes → Consolidation
    # → Pattern/Context/Insight refinement → Memory Ledger.
    learning_loop_store = LearningLoopStore(
        decision_store=decision_read_store,
        recommendation_store=recommendation_read_store,
        hypothesis_store=hypothesis_store,
        pattern_store=pattern_read_store,
        context_store=context_read_store,
        insight_store=insight_store,
        memory_store=memory_store,
    )
    await learning_loop_store.verify_connection()

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
        context_revision_store=context_revision_store,
        insight_transformation_store=insight_transformation_store,
        memory_store=memory_store,
        timeline_store=timeline_store,
        learning_loop_store=learning_loop_store,
        service_health=_build_service_health(),
        dsn=dsn,
        blacklist=blacklist,
        confidence_store=confidence_store,
        machine_jwt=machine_jwt,
    )
    server = GatewayServer(service, jwt, machine_jwt=machine_jwt)

    # Observation Publisher (ADR-0004 §4): outbox → Redis Streams
    from libs.cognitive_core.observation_bus import ObservationBus
    from libs.telemetry.publisher import ObservationPublisher
    from redis.asyncio import from_url as redis_from_url

    redis_client = redis_from_url(redis_url)
    observation_bus = ObservationBus(redis_client)
    publisher = ObservationPublisher(dsn, observation_bus)
    await publisher.start()

    # Heartbeat Reconciler (ADR-0006 §9): stale RUNNING → STOPPED
    from src.reconciler import HeartbeatReconciler

    reconciler = HeartbeatReconciler(dsn)
    await reconciler.start()

    await server.start(port)

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await reconciler.stop()
        await publisher.stop()
        await server.stop()
        await engine.dispose()
        await decision_store.close()
        await report_store.close()
        await cognitive_trace_store.close()
        await memory_store.close()
        await evidence_store.close()
        await anomaly_store.close()
        await learning_loop_store.close()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
