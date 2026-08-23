"""Integration tests for Confidence persistence, the Calibrate cycle and traceability.

Requires the sandbox infra (postgres at 127.0.0.1:5433). Cleanup disables the
P1/immutability triggers with session_replication_role = replica (superuser)
and deletes the child tables first (the content triggers block plain DELETEs).
"""
import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import asyncpg
import pytest
from libs.cognitive_core.calibration_model import CalibrationParams
from libs.learning.confidence import ConfidenceCreate, ConfidenceStore, build_confidence
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
from src.service import ConfidenceService

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
PARAMS = CalibrationParams()


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"conf-{tenant_id}",
            f"confslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
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


def make_context(
    tenant_id: uuid.UUID, model_id: str, purpose: str, ctx_id: uuid.UUID
) -> Context:
    return Context(
        id=ctx_id,
        tenant_id=tenant_id,
        evidence_ids=[uuid.uuid4()],
        mental_model_id=model_id,
        purpose=purpose,
        coherence_score=0.7,
        competing_models=[],
        activated_at=NOW,
    )


async def _seed_traceability(
    tenant_id: uuid.UUID,
    context_store: ContextStore,
    evidence_store: EvidenceStore,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed observation -> evidence -> context for a sandboxed tenant.

    Returns (context_id, evidence_id).
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
    ctx = make_context(tenant_id, "resource_pressure", "infrastructure_health", ctx_id)
    ctx = ctx.model_copy(update={"evidence_ids": [evidence.id]})
    await context_store.save_context(ctx)

    return ctx_id, evidence.id


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


def make_confidence_create(
    tenant_id: uuid.UUID, target_id: uuid.UUID, **overrides
) -> ConfidenceCreate:
    base = {
        "tenant_id": tenant_id,
        "target_type": "hypothesis",
        "target_id": target_id,
        "evidential_support": 0.7,
        "explanatory_coherence": 0.8,
        "historical_calibration": 1.0,
        "confidence_score": 0.75,
        "alpha": 0.5,
        "calibration_justification": "justificacion",
        "calibration_error_estimate": 0.0,
        "computed_at": NOW,
    }
    base.update(overrides)
    return ConfidenceCreate(**base)


async def test_confidence_insert_read_back_and_fields_persisted(confidence_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        target_id = uuid.uuid4()
        create = build_confidence(
            make_confidence_create(
                tenant_id,
                target_id,
                evidential_support=0.8176,
                explanatory_coherence=0.6667,
                historical_calibration=1.0,
                confidence_score=0.7421,
                alpha=0.5,
                calibration_justification="justificacion integrada",
                calibration_error_estimate=0.0,
            )
        )
        row = await confidence_store.save_confidence(create)
        assert row is not None
        assert row["id"] == create.id
        assert row["target_type"] == "hypothesis"

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT evidential_support, explanatory_coherence, "
                "       historical_calibration, confidence_score, alpha, "
                "       calibration_justification, calibration_error_estimate "
                "FROM confidence_scores WHERE id = $1",
                create.id,
            )
        finally:
            await conn.close()
        assert float(selected["evidential_support"]) == 0.8176
        assert float(selected["explanatory_coherence"]) == 0.6667
        assert float(selected["historical_calibration"]) == 1.0
        assert float(selected["confidence_score"]) == 0.7421
        assert float(selected["alpha"]) == 0.5
        assert selected["calibration_justification"] == "justificacion integrada"
        assert float(selected["calibration_error_estimate"]) == 0.0

        loaded = await confidence_store.list_confidence(tenant_id=tenant_id)
        assert create.id in {c.id for c in loaded}
        assert tenant_id in (await confidence_store.list_tenant_ids())
    finally:
        await _cleanup_tenant(tenant_id)


async def test_confidence_save_is_idempotent_and_recalibration_appends(confidence_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        target_id = uuid.uuid4()
        first = build_confidence(
            make_confidence_create(tenant_id, target_id, evidential_support=0.7)
        )
        assert (await confidence_store.save_confidence(first)) is not None
        # Identical inputs -> same id -> dedup, no new row.
        assert (await confidence_store.save_confidence(first)) is None

        # New calibration inputs -> content-addressed id changes -> a NEW row is
        # appended (P1: the historical calibration is preserved, never overwritten).
        second = build_confidence(
            make_confidence_create(
                tenant_id, target_id, evidential_support=0.6, computed_at=NOW + timedelta(minutes=1)
            )
        )
        assert second.id != first.id
        assert (await confidence_store.save_confidence(second)) is not None

        rows = await confidence_store.list_confidence(tenant_id=tenant_id)
        assert len(rows) == 2
        latest = await confidence_store.get_confidence(
            target_type="hypothesis", target_id=target_id
        )
        assert latest is not None
        assert latest.id == second.id
    finally:
        await _cleanup_tenant(tenant_id)


async def test_confidence_content_trigger_blocks_update_and_delete(confidence_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        create = build_confidence(
            make_confidence_create(tenant_id, uuid.uuid4())
        )
        await confidence_store.save_confidence(create)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE confidence_scores SET confidence_score = 0.9 WHERE id = $1",
                    create.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE confidence_scores SET calibration_justification = 'x' "
                    "WHERE id = $1",
                    create.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute("DELETE FROM confidence_scores WHERE id = $1", create.id)
        finally:
            await conn.close()
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_calibrates_hypotheses_with_traceability_and_p1(
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
):
    """End-to-end: hypotheses + knowledge stream -> calibrated confidence rows."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx_id, _ = await _seed_traceability(tenant_id, context_store, evidence_store)
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

        # Three candidate hypotheses over the same anomaly (Sprint 7 artifacts).
        for description in (
            "Hipotesis candidata de saturacion de disco.",
            "Hipotesis candidata de retencion de logs.",
            "Hipotesis candidata de auto-growth.",
        ):
            create = HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=[anomaly.id],
                pattern_ids=[pattern_id],
                description=description,
                predicted_consequences=["Consecuencia observable."],
                falsification_criterion="Si no se observa, se descarta.",
                coherence_score=0.5,
                status=STATUS_CANDIDATE,
            )
            await hypothesis_store.save_hypothesis(build_hypothesis(create))

        service = ConfidenceService(
            hypothesis_store,
            anomaly_store,
            context_store,
            evidence_store,
            confidence_store,
            params=PARAMS,
        )
        calibrated = await service.run_calibration_cycle()
        assert calibrated >= 3
        assert service.errors == 0

        conn = await asyncpg.connect(DSN_RAW)
        try:
            rows = await conn.fetch(
                "SELECT c.id, c.target_id, c.evidential_support, "
                "       c.explanatory_coherence, c.historical_calibration, "
                "       c.confidence_score, c.alpha, c.calibration_justification, "
                "       c.calibration_error_estimate "
                "FROM confidence_scores c "
                "JOIN hypotheses h ON h.id = c.target_id "
                "WHERE c.tenant_id = $1 AND c.target_type = 'hypothesis'",
                tenant_id,
            )
            trace = await conn.fetch(
                "SELECT c.id AS confidence_id, h.id AS hypothesis_id, "
                "       a.id AS anomaly_id, p.id AS pattern_id, "
                "       ctx.id AS context_id, e.id AS evidence_id, "
                "       o.id AS observation_id "
                "FROM confidence_scores c "
                "JOIN hypotheses h ON h.id = c.target_id "
                "JOIN anomalies a ON a.id = ANY(h.anomaly_ids) "
                "JOIN patterns p ON p.id = a.pattern_id "
                "JOIN contexts ctx ON ctx.id = a.context_id "
                "JOIN evidence e ON e.id = ANY(ctx.evidence_ids) "
                "JOIN observations o ON o.id = ANY(e.observation_ids) "
                "WHERE c.tenant_id = $1 AND c.target_type = 'hypothesis'",
                tenant_id,
            )
            unchanged = await conn.fetchrow(
                "SELECT (SELECT count(*) FROM observations WHERE tenant_id = $1) AS obs,"
                "       (SELECT count(*) FROM evidence WHERE tenant_id = $1) AS ev,"
                "       (SELECT count(*) FROM contexts WHERE tenant_id = $1) AS ctx,"
                "       (SELECT count(*) FROM patterns WHERE tenant_id = $1) AS pat,"
                "       (SELECT count(*) FROM anomalies WHERE tenant_id = $1) AS ano,"
                "       (SELECT count(*) FROM hypotheses WHERE tenant_id = $1) AS hyp",
                tenant_id,
            )
        finally:
            await conn.close()

        assert len(rows) >= 3, "every candidate hypothesis gets a calibrated confidence"
        for row in rows:
            assert 0.0 <= float(row["evidential_support"]) <= 1.0
            assert 0.0 <= float(row["explanatory_coherence"]) <= 1.0
            assert float(row["historical_calibration"]) == 1.0  # first data, ECE=0
            assert 0.0 <= float(row["confidence_score"]) <= 1.0
            assert float(row["alpha"]) == 0.5
            assert float(row["calibration_error_estimate"]) == 0.0
            assert row["calibration_justification"] and "C_final=" in row["calibration_justification"]

        # Traceability: confidence -> hypothesis -> anomaly -> pattern -> context
        # -> evidence -> observations.
        assert len(trace) >= 3
        assert all(row["anomaly_id"] == anomaly.id for row in trace)
        assert all(row["pattern_id"] == pattern_id for row in trace)

        # Re-running the cycle must not duplicate rows (idempotent dedup).
        await service.run_calibration_cycle()
        assert service.total_duplicates >= 1
        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM confidence_scores WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == len(rows)

        # P1: perception + reasoning artifacts are untouched by the Calibrate cycle.
        assert unchanged["obs"] == 2
        assert unchanged["ev"] == 1
        assert unchanged["ctx"] == 1
        assert unchanged["pat"] == 1
        assert unchanged["ano"] == 1
        assert unchanged["hyp"] == len(rows)
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_without_hypotheses_is_clean(confidence_store):
    """No hypotheses -> zero confidence rows and zero errors."""
    service = ConfidenceService(
        HypothesisStore(DSN_STORE),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        confidence_store,
        params=PARAMS,
    )
    await service.hypothesis_store.verify_connection()
    calibrated = await service.run_calibration_cycle()
    assert calibrated == 0
    assert service.errors == 0
    assert service.total_confidence_scores == 0
    await service.hypothesis_store.close()


def test_confidence_service_metrics_are_exposed():
    from types import SimpleNamespace

    service = ConfidenceService.__new__(ConfidenceService)
    service.total_confidence_scores = 4
    service.total_duplicates = 1
    service.errors = 0
    service.by_target_type = {"hypothesis": 4}
    # Use the new _RunningStats attributes
    service._confidence_stats = SimpleNamespace(mean_value=0.75)
    service._error_stats = SimpleNamespace(mean_value=0.1)
    service.last_run_at = None
    # Mock confidence store for health check
    mock_store = SimpleNamespace(
        verify_connection=lambda: None,
    )
    health = HealthServer(service, mock_store)

    async def get_metrics():
        response = await health.metrics_handler(SimpleNamespace())
        body = json.loads(response.body)
        assert body["total_confidence_scores"] == 4
        assert body["total_confidence_duplicates"] == 1
        assert body["total_errors"] == 0
        assert body["confidence_by_target_type"]["hypothesis"] == 4
        assert body["mean_confidence_score"] == 0.75
        assert body["mean_calibration_error_estimate"] == 0.1

    asyncio.run(get_metrics())