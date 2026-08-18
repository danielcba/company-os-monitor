"""Integration tests for Decision persistence, the Commit cycle and traceability.

Requires the sandbox infra (postgres at 127.0.0.1:5433) and the Sprint 10
content trigger applied. Cleanup disables the P1/immutability triggers with
session_replication_role = replica (superuser) and deletes the child tables
first (the content triggers block plain DELETEs).
"""
import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import asyncpg
import pytest
from libs.action.decision import (
    STATUS_COMMITTED,
    DecisionStore,
)
from libs.action.recommendation import (
    STATUS_PROPOSED,
    Recommendation,
    RecommendationStore,
)
from libs.learning.confidence import Confidence, ConfidenceStore
from libs.perception.context import Context, ContextStore
from libs.perception.evidence import EvidenceStore, build_evidence
from libs.perception.observation import EvidenceCreate, QualityClass
from libs.reasoning.anomaly import Anomaly, AnomalyStore
from libs.reasoning.hypothesis import (
    STATUS_CANDIDATE,
    HypothesisCreate,
    HypothesisStore,
    build_hypothesis,
)
from libs.reasoning.pattern import Pattern, PatternStore

from src.health import HealthServer
from src.service import DecisionService

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"dec-{tenant_id}",
            f"decslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute("DELETE FROM decisions WHERE tenant_id = $1", tenant_id)
        await conn.execute(
            "DELETE FROM recommendations WHERE tenant_id = $1", tenant_id
        )
        await conn.execute(
            "DELETE FROM confidence_scores WHERE tenant_id = $1", tenant_id
        )
        await conn.execute("DELETE FROM hypotheses WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM insights WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM anomalies WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM patterns WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM contexts WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM evidence WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM observations WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
        await conn.execute("SET session_replication_role = origin")
    finally:
        await conn.close()


@pytest.fixture
async def decision_store():
    instance = DecisionStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def recommendation_store():
    instance = RecommendationStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def confidence_store():
    instance = ConfidenceStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def hypothesis_store():
    instance = HypothesisStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def anomaly_store():
    instance = AnomalyStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def context_store():
    instance = ContextStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def evidence_store():
    instance = EvidenceStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def pattern_store():
    instance = PatternStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


async def _seed_traceability(
    tenant_id: uuid.UUID,
    context_store: ContextStore,
    evidence_store: EvidenceStore,
    anomaly_store: AnomalyStore,
    pattern_store: PatternStore,
) -> tuple[uuid.UUID, uuid.UUID, Anomaly, uuid.UUID]:
    """Seed observation -> evidence -> context -> pattern -> anomaly.

    Returns (context_id, evidence_id, anomaly, pattern_id).
    """
    conn = await asyncpg.connect(DSN_RAW)
    obs_ids = []
    try:
        for _ in range(2):
            obs_id = uuid.uuid4()
            obs_ids.append(obs_id)
            await conn.execute(
                "INSERT INTO observations ("
                " id, tenant_id, source_id, source_type, fact_type, fact_value,"
                " unit, captured_at, quality_class, raw_payload)"
                " VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10::jsonb)",
                obs_id,
                tenant_id,
                uuid.uuid4(),
                "linux_agent",
                "disk_usage_percent",
                '{"value": 0.88}',
                "percent",
                NOW - timedelta(days=2),
                "Q1",
                '{"raw": true}',
            )
    finally:
        await conn.close()

    evidence = build_evidence(
        EvidenceCreate(
            tenant_id=tenant_id,
            observation_ids=obs_ids,
            organization_type="resource_exhaustion_evidence",
            description="organizacion factual",
            quality_class=QualityClass.Q1,
            weight=0.88,
        )
    )
    await evidence_store.save_evidence(evidence)

    ctx_id = uuid.uuid4()
    ctx = Context(
        id=ctx_id,
        tenant_id=tenant_id,
        evidence_ids=[evidence.id],
        mental_model_id="resource_pressure",
        purpose="infrastructure_health",
        coherence_score=0.7,
        competing_models=[],
        activated_at=NOW,
        is_active=True,
    )
    await context_store.save_context(ctx)

    pattern_id = uuid.uuid4()
    pattern = Pattern(
        id=pattern_id,
        tenant_id=tenant_id,
        context_id=ctx_id,
        pattern_type="temporal",
        description="Regularidad detectada.",
        strength_measure=0.9,
        frequency="daily",
        detected_at=NOW,
        is_active=True,
    )
    await pattern_store.save_pattern(pattern)

    anomaly = Anomaly(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        context_id=ctx_id,
        pattern_id=pattern_id,
        deviation_score=2.5,
        tolerance_threshold=1.0,
        anomaly_class="point",
        detected_at=NOW,
    )
    await anomaly_store.save_anomaly(anomaly)

    return ctx_id, evidence.id, anomaly, pattern_id


async def _seed_recommendation(
    tenant_id: uuid.UUID,
    recommendation_store: RecommendationStore,
    hypothesis_store: HypothesisStore,
    confidence_store: ConfidenceStore,
    anomaly: Anomaly,
    pattern_id: uuid.UUID,
    confidence_score: float = 0.8,
) -> tuple[Recommendation, Confidence]:
    """Seed hypothesis + calibrated Confidence + proposed Recommendation."""
    create = HypothesisCreate(
        tenant_id=tenant_id,
        anomaly_ids=[anomaly.id],
        pattern_ids=[pattern_id],
        description="Hipótesis candidata de saturación de disco.",
        predicted_consequences=["El volumen persistido seguirá creciendo."],
        falsification_criterion="Si no se observa, se descarta.",
        coherence_score=0.5,
        status=STATUS_CANDIDATE,
    )
    hypothesis = build_hypothesis(create)
    await hypothesis_store.save_hypothesis(hypothesis)

    confidence = Confidence(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        target_type="hypothesis",
        target_id=hypothesis.id,
        evidential_support=0.7,
        explanatory_coherence=0.8,
        historical_calibration=1.0,
        confidence_score=confidence_score,
        alpha=0.5,
        calibration_justification="S=0.7000, C=0.8000, ECE=0.0000, C_final=0.8.",
        calibration_error_estimate=0.0,
        computed_at=NOW,
    )
    await confidence_store.save_confidence(confidence)

    recommendation = Recommendation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        hypothesis_id=hypothesis.id,
        insight_id=None,
        confidence_id=confidence.id,
        action_description=(
            "Expandir el volumen objetivo del almacenamiento antes del umbral "
            "proyectado, o mover los datos a un destino con espacio disponible."
        ),
        rationale="Derivada de la hipótesis y su confidence calibrada.",
        expected_consequences=[
            (
                "El espacio libre del volumen objetivo permanecerá por encima del "
                "umbral documentado durante los próximos 90 días."
            )
        ],
        alternatives_considered=[
            {
                "action": "compress",
                "rationale": "Menor coste inmediato.",
                "rejected_reason": "Puede no acompañar el ritmo de crecimiento.",
                "confidence": confidence_score,
            },
            {
                "action": "purge_old",
                "rationale": "Libera espacio eliminando datos viejos.",
                "rejected_reason": "Riesgo de retención.",
                "confidence": confidence_score,
            },
        ],
        confidence_score=confidence_score,
        status=STATUS_PROPOSED,
        proposed_at=NOW,
    )
    await recommendation_store.save_recommendation(recommendation)
    return recommendation, confidence


async def test_decision_insert_read_back_and_fields_persisted(
    decision_store,
    recommendation_store,
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        _, _, anomaly, pattern_id = await _seed_traceability(
            tenant_id, context_store, evidence_store, anomaly_store, pattern_store
        )
        recommendation, confidence = await _seed_recommendation(
            tenant_id,
            recommendation_store,
            hypothesis_store,
            confidence_store,
            anomaly,
            pattern_id,
            confidence_score=0.8,
        )

        service = DecisionService(
            recommendation_store, confidence_store, decision_store
        )
        committed = await service.run_decision_cycle()
        assert committed == 1
        assert service.errors == 0
        assert service.total_recommendations_below_confidence == 0

        rows = await decision_store.list_decisions(tenant_id=tenant_id)
        assert len(rows) == 1
        decision = rows[0]
        assert decision.status == STATUS_COMMITTED
        assert decision.recommendation_id == recommendation.id
        assert decision.confidence_id == confidence.id
        assert decision.authority_id is not None
        assert decision.risk_tolerance in {"low", "medium", "high"}
        assert decision.executed_at is None
        assert decision.actual_outcomes is None

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT commitment, risk_tolerance, status, authority_id, "
                "       committed_at, expected_outcomes "
                "FROM decisions WHERE id = $1",
                decision.id,
            )
            trace = await conn.fetch(
                "SELECT d.id AS decision_id, r.id AS recommendation_id, "
                "       h.id AS hypothesis_id, c.id AS confidence_id, "
                "       a.id AS anomaly_id, p.id AS pattern_id, "
                "       ctx.id AS context_id, e.id AS evidence_id, "
                "       o.id AS observation_id "
                "FROM decisions d "
                "JOIN recommendations r ON r.id = d.recommendation_id "
                "JOIN hypotheses h ON h.id = r.hypothesis_id "
                "JOIN confidence_scores c ON c.id = d.confidence_id "
                "JOIN anomalies a ON a.id = ANY(h.anomaly_ids) "
                "JOIN patterns p ON p.id = a.pattern_id "
                "JOIN contexts ctx ON ctx.id = a.context_id "
                "JOIN evidence e ON e.id = ANY(ctx.evidence_ids) "
                "JOIN observations o ON o.id = ANY(e.observation_ids) "
                "WHERE d.tenant_id = $1",
                tenant_id,
            )
        finally:
            await conn.close()

        outcomes = (
            selected["expected_outcomes"]
            if isinstance(selected["expected_outcomes"], list)
            else json.loads(selected["expected_outcomes"])
        )
        assert len(outcomes) >= 1
        for outcome in outcomes:
            assert outcome.get("prediction")
            assert outcome.get("verifiable_by")
            assert outcome.get("deadline")
        assert selected["status"] == STATUS_COMMITTED
        assert selected["risk_tolerance"] == decision.risk_tolerance
        assert selected["authority_id"] == decision.authority_id
        # Definitive commitment: no vague intention, no trailing alternative.
        assert " o " not in selected["commitment"]
        assert "probably" not in selected["commitment"].lower()
        # Full trace: decision -> recommendation -> hypothesis -> confidence ->
        # anomaly -> pattern -> context -> evidence -> observations.
        assert len(trace) >= 1
        assert all(row["decision_id"] == decision.id for row in trace)
        assert all(row["recommendation_id"] == recommendation.id for row in trace)
        assert all(row["confidence_id"] == confidence.id for row in trace)
        assert all(row["anomaly_id"] == anomaly.id for row in trace)
        assert all(row["pattern_id"] == pattern_id for row in trace)
    finally:
        await _cleanup_tenant(tenant_id)


async def test_decision_save_is_idempotent(
    decision_store,
    recommendation_store,
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        _, _, anomaly, pattern_id = await _seed_traceability(
            tenant_id, context_store, evidence_store, anomaly_store, pattern_store
        )
        _recommendation, _ = await _seed_recommendation(
            tenant_id,
            recommendation_store,
            hypothesis_store,
            confidence_store,
            anomaly,
            pattern_id,
            confidence_score=0.8,
        )

        service = DecisionService(
            recommendation_store, confidence_store, decision_store
        )
        assert await service.run_decision_cycle() == 1
        # Identical inputs -> same deterministic id -> dedup, no new row.
        assert await service.run_decision_cycle() == 1
        assert service.total_duplicates == 1

        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM decisions WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_below_confidence_yields_no_decision_and_metric(
    decision_store,
    recommendation_store,
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        _, _, anomaly, pattern_id = await _seed_traceability(
            tenant_id, context_store, evidence_store, anomaly_store, pattern_store
        )
        await _seed_recommendation(
            tenant_id,
            recommendation_store,
            hypothesis_store,
            confidence_store,
            anomaly,
            pattern_id,
            confidence_score=0.7,  # below the 0.75 commit threshold
        )

        service = DecisionService(
            recommendation_store, confidence_store, decision_store
        )
        assert await service.run_decision_cycle() == 0
        assert service.total_recommendations_below_confidence == 1
        assert service.errors == 0

        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM decisions WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == 0
    finally:
        await _cleanup_tenant(tenant_id)


async def test_decision_content_trigger_blocks_content_change_but_allows_lifecycle(
    decision_store,
    recommendation_store,
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        _, _, anomaly, pattern_id = await _seed_traceability(
            tenant_id, context_store, evidence_store, anomaly_store, pattern_store
        )
        _, _ = await _seed_recommendation(
            tenant_id,
            recommendation_store,
            hypothesis_store,
            confidence_store,
            anomaly,
            pattern_id,
            confidence_score=0.8,
        )

        service = DecisionService(
            recommendation_store, confidence_store, decision_store
        )
        await service.run_decision_cycle()
        decision = (await decision_store.list_decisions(tenant_id=tenant_id))[0]

        conn = await asyncpg.connect(DSN_RAW)
        try:
            # Lifecycle: status is flippable (committed -> executing/completed).
            await conn.execute(
                "UPDATE decisions SET status = $1 WHERE id = $2",
                "executing",
                decision.id,
            )
            # Lifecycle: executed_at and actual_outcomes are populated ONLY by
            # the Learning loop (future phase) - allowed by the trigger.
            await conn.execute(
                "UPDATE decisions SET status = $1, executed_at = $2, "
                "actual_outcomes = $3::jsonb WHERE id = $4",
                "completed",
                NOW,
                '[{"prediction": "p", "observed": true}]',
                decision.id,
            )
            # Content is immutable (P1): blocked by the trigger.
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE decisions SET commitment = 'x' WHERE id = $1",
                    decision.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE decisions SET expected_outcomes = '[]'::jsonb "
                    "WHERE id = $1",
                    decision.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE decisions SET risk_tolerance = 'high' WHERE id = $1",
                    decision.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "DELETE FROM decisions WHERE id = $1", decision.id
                )
        finally:
            await conn.close()
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_leaves_previous_artifacts_unchanged_p1(
    decision_store,
    recommendation_store,
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        _, _, anomaly, pattern_id = await _seed_traceability(
            tenant_id, context_store, evidence_store, anomaly_store, pattern_store
        )
        await _seed_recommendation(
            tenant_id,
            recommendation_store,
            hypothesis_store,
            confidence_store,
            anomaly,
            pattern_id,
            confidence_score=0.8,
        )

        conn = await asyncpg.connect(DSN_RAW)
        try:
            before = await conn.fetchrow(
                "SELECT (SELECT count(*) FROM observations WHERE tenant_id = $1) AS obs,"
                "       (SELECT count(*) FROM evidence WHERE tenant_id = $1) AS ev,"
                "       (SELECT count(*) FROM contexts WHERE tenant_id = $1) AS ctx,"
                "       (SELECT count(*) FROM patterns WHERE tenant_id = $1) AS pat,"
                "       (SELECT count(*) FROM anomalies WHERE tenant_id = $1) AS ano,"
                "       (SELECT count(*) FROM hypotheses WHERE tenant_id = $1) AS hyp,"
                "       (SELECT count(*) FROM confidence_scores WHERE tenant_id = $1) AS conf,"
                "       (SELECT count(*) FROM recommendations WHERE tenant_id = $1) AS rec",
                tenant_id,
            )
        finally:
            await conn.close()

        service = DecisionService(
            recommendation_store, confidence_store, decision_store
        )
        await service.run_decision_cycle()

        conn = await asyncpg.connect(DSN_RAW)
        try:
            after = await conn.fetchrow(
                "SELECT (SELECT count(*) FROM observations WHERE tenant_id = $1) AS obs,"
                "       (SELECT count(*) FROM evidence WHERE tenant_id = $1) AS ev,"
                "       (SELECT count(*) FROM contexts WHERE tenant_id = $1) AS ctx,"
                "       (SELECT count(*) FROM patterns WHERE tenant_id = $1) AS pat,"
                "       (SELECT count(*) FROM anomalies WHERE tenant_id = $1) AS ano,"
                "       (SELECT count(*) FROM hypotheses WHERE tenant_id = $1) AS hyp,"
                "       (SELECT count(*) FROM confidence_scores WHERE tenant_id = $1) AS conf,"
                "       (SELECT count(*) FROM recommendations WHERE tenant_id = $1) AS rec",
                tenant_id,
            )
        finally:
            await conn.close()

        # P1: the Commit capability only APPENDS to `decisions`; every previous
        # artifact is untouched (append-only, never written by this service).
        assert dict(before) == dict(after)
    finally:
        await _cleanup_tenant(tenant_id)


async def test_list_decisions_by_status_for_learning_loop(
    decision_store,
    recommendation_store,
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
):
    """Gate para Sprint 11: DecisionStore expone reads por status y período."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        _, _, anomaly, pattern_id = await _seed_traceability(
            tenant_id, context_store, evidence_store, anomaly_store, pattern_store
        )
        await _seed_recommendation(
            tenant_id,
            recommendation_store,
            hypothesis_store,
            confidence_store,
            anomaly,
            pattern_id,
            confidence_score=0.8,
        )
        service = DecisionService(
            recommendation_store, confidence_store, decision_store
        )
        await service.run_decision_cycle()

        committed = await decision_store.list_decisions_by_status(
            tenant_id=tenant_id, status=STATUS_COMMITTED
        )
        assert len(committed) == 1
        assert committed[0].status == STATUS_COMMITTED
        executing = await decision_store.list_decisions_by_status(
            tenant_id=tenant_id, status="executing"
        )
        assert executing == []
        assert tenant_id in (await decision_store.list_tenant_ids())
    finally:
        await _cleanup_tenant(tenant_id)


def test_decision_service_metrics_are_exposed():
    service = DecisionService.__new__(DecisionService)
    service.total_decisions = 3
    service.total_duplicates = 1
    service.total_recommendations_below_confidence = 2
    service.total_recommendations_skipped = 0
    service.errors = 0
    service.by_status = {"committed": 3}
    service.by_risk_tolerance = {"medium": 3}
    service.last_run_at = None
    health = HealthServer(service)

    async def get_metrics():
        response = await health.metrics_handler(SimpleNamespace())
        body = json.loads(response.body)
        assert body["total_decisions"] == 3
        assert body["total_decision_duplicates"] == 1
        assert body["total_recommendations_below_confidence"] == 2
        assert body["total_errors"] == 0
        assert body["decisions_by_status"] == {"committed": 3}
        assert body["decisions_by_risk_tolerance"] == {"medium": 3}

    asyncio.run(get_metrics())