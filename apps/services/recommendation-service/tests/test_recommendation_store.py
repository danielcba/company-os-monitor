"""Integration tests for Recommendation persistence, the Propose cycle and traceability.

Requires the sandbox infra (postgres at 127.0.0.1:5433) and the Sprint 9
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
from libs.action.recommendation import (
    STATUS_ACCEPTED,
    STATUS_PROPOSED,
    RecommendationStore,
)
from libs.learning.confidence import ConfidenceCreate, ConfidenceStore, build_confidence
from libs.perception.context import Context, ContextStore
from libs.perception.evidence import EvidenceStore, build_evidence
from libs.perception.observation import EvidenceCreate, QualityClass
from libs.procedural_memory.action_space import ACTION_SPACE_LIBRARY
from libs.reasoning.anomaly import Anomaly, AnomalyStore
from libs.reasoning.hypothesis import (
    STATUS_CANDIDATE,
    HypothesisCreate,
    HypothesisStore,
    build_hypothesis,
)
from libs.reasoning.pattern import Pattern, PatternStore

from src.health import HealthServer
from src.service import RecommendationService

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
            f"rec-{tenant_id}",
            f"recslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
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


def make_confidence_create(tenant_id, target_id, **overrides) -> ConfidenceCreate:
    base = {
        "tenant_id": tenant_id,
        "target_type": "hypothesis",
        "target_id": target_id,
        "evidential_support": 0.7,
        "explanatory_coherence": 0.8,
        "historical_calibration": 1.0,
        "confidence_score": 0.75,
        "alpha": 0.5,
        "calibration_justification": "S=0.7000, C=0.8000, ECE=0.0000, C_final=0.7500.",
        "calibration_error_estimate": 0.0,
        "computed_at": NOW,
    }
    base.update(overrides)
    return ConfidenceCreate(**base)


async def test_recommendation_insert_read_back_and_fields_persisted(
    recommendation_store,
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        conn = await asyncpg.connect(DSN_RAW)
        try:
            hypothesis_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO hypotheses ("
                " id, tenant_id, anomaly_ids, pattern_ids, description,"
                " predicted_consequences, falsification_criterion, coherence_score,"
                " status, generated_at)"
                " VALUES ($1, $2, $3::uuid[], $4::uuid[], $5, $6::jsonb, $7, $8, $9, $10)",
                hypothesis_id,
                tenant_id,
                [],
                [],
                "Hipotesis sembrada.",
                '["Consecuencia observable."]',
                "Criterio de falsificacion.",
                0.5,
                STATUS_CANDIDATE,
                NOW,
            )
            confidence_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO confidence_scores ("
                " id, tenant_id, target_type, target_id, evidential_support,"
                " explanatory_coherence, historical_calibration, confidence_score,"
                " alpha, calibration_justification, calibration_error_estimate, computed_at)"
                " VALUES ($1, $2, 'hypothesis', $3, 0.7, 0.8, 1.0, 0.7421,"
                " 0.5, 'justificacion', 0.0, $4)",
                confidence_id,
                tenant_id,
                hypothesis_id,
                NOW,
            )
        finally:
            await conn.close()

        from libs.action.recommendation import Recommendation

        recommendation = Recommendation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            hypothesis_id=hypothesis_id,
            insight_id=None,
            confidence_id=confidence_id,
            action_description="Expandir el volumen objetivo del almacenamiento.",
            rationale="Derivada de la hipótesis y su confidence calibrada.",
            expected_consequences=[
                "El espacio libre permanecerá por encima del umbral durante 90 días."
            ],
            alternatives_considered=[
                {
                    "action": "compress",
                    "rationale": "Menor coste inmediato.",
                    "rejected_reason": "Puede no acompañar el ritmo de crecimiento.",
                    "confidence": 0.7421,
                }
            ],
            confidence_score=0.7421,
            status=STATUS_PROPOSED,
            proposed_at=NOW,
        )
        row = await recommendation_store.save_recommendation(recommendation)
        assert row is not None
        assert row["id"] == recommendation.id
        assert row["hypothesis_id"] == hypothesis_id
        assert row["confidence_id"] == confidence_id
        assert row["status"] == STATUS_PROPOSED

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT action_description, rationale, confidence_score, status, "
                "       proposed_at, confidence_id "
                "FROM recommendations WHERE id = $1",
                recommendation.id,
            )
        finally:
            await conn.close()
        assert selected["action_description"] == recommendation.action_description
        assert selected["rationale"] == recommendation.rationale
        assert float(selected["confidence_score"]) == 0.7421
        assert selected["status"] == STATUS_PROPOSED
        assert selected["confidence_id"] == confidence_id

        loaded = await recommendation_store.list_recommendations(tenant_id=tenant_id)
        assert len(loaded) == 1
        loaded_rec = loaded[0]
        assert loaded_rec.id == recommendation.id
        assert loaded_rec.expected_consequences == recommendation.expected_consequences
        assert loaded_rec.alternatives_considered == recommendation.alternatives_considered
        assert tenant_id in (await recommendation_store.list_tenant_ids())
    finally:
        await _cleanup_tenant(tenant_id)


async def test_recommendation_save_is_idempotent(recommendation_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        conn = await asyncpg.connect(DSN_RAW)
        try:
            hypothesis_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO hypotheses ("
                " id, tenant_id, anomaly_ids, pattern_ids, description,"
                " predicted_consequences, falsification_criterion, coherence_score,"
                " status, generated_at)"
                " VALUES ($1, $2, $3::uuid[], $4::uuid[], $5, $6::jsonb, $7, $8, $9, $10)",
                hypothesis_id,
                tenant_id,
                [],
                [],
                "H",
                '["C"]',
                "F",
                0.5,
                "candidate",
                NOW,
            )
            confidence_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO confidence_scores ("
                " id, tenant_id, target_type, target_id, evidential_support,"
                " explanatory_coherence, historical_calibration, confidence_score,"
                " alpha, calibration_justification, calibration_error_estimate, computed_at)"
                " VALUES ($1, $2, 'hypothesis', $3, 0.7, 0.8, 1.0, 0.75,"
                " 0.5, 'j', 0.0, $4)",
                confidence_id,
                tenant_id,
                hypothesis_id,
                NOW,
            )
        finally:
            await conn.close()

        from libs.action.recommendation import Recommendation

        recommendation = Recommendation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            hypothesis_id=hypothesis_id,
            insight_id=None,
            confidence_id=confidence_id,
            action_description="Cambiar el destino de backup al arreglo alternativo.",
            rationale="Derivada de la hipótesis y su confidence calibrada.",
            expected_consequences=["El destino alternativo mantendrá espacio libre."],
            alternatives_considered=[],
            confidence_score=0.75,
            status=STATUS_PROPOSED,
            proposed_at=NOW,
        )
        assert (await recommendation_store.save_recommendation(recommendation)) is not None
        # Identical inputs -> same id -> dedup, no new row.
        assert (await recommendation_store.save_recommendation(recommendation)) is None
        rows = await recommendation_store.list_recommendations(tenant_id=tenant_id)
        assert len(rows) == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_recommendation_content_trigger_blocks_content_change_but_allows_status(
    recommendation_store,
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        conn = await asyncpg.connect(DSN_RAW)
        try:
            hypothesis_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO hypotheses ("
                " id, tenant_id, anomaly_ids, pattern_ids, description,"
                " predicted_consequences, falsification_criterion, coherence_score,"
                " status, generated_at)"
                " VALUES ($1, $2, $3::uuid[], $4::uuid[], $5, $6::jsonb, $7, $8, $9, $10)",
                hypothesis_id,
                tenant_id,
                [],
                [],
                "H",
                '["C"]',
                "F",
                0.5,
                "candidate",
                NOW,
            )
            confidence_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO confidence_scores ("
                " id, tenant_id, target_type, target_id, evidential_support,"
                " explanatory_coherence, historical_calibration, confidence_score,"
                " alpha, calibration_justification, calibration_error_estimate, computed_at)"
                " VALUES ($1, $2, 'hypothesis', $3, 0.7, 0.8, 1.0, 0.75,"
                " 0.5, 'j', 0.0, $4)",
                confidence_id,
                tenant_id,
                hypothesis_id,
                NOW,
            )
        finally:
            await conn.close()

        from libs.action.recommendation import Recommendation

        recommendation = Recommendation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            hypothesis_id=hypothesis_id,
            insight_id=None,
            confidence_id=confidence_id,
            action_description="Resetear las credenciales de la cuenta afectada.",
            rationale="Derivada de la hipótesis y su confidence calibrada.",
            expected_consequences=["La cuenta dejará de presentar fallos."],
            alternatives_considered=[],
            confidence_score=0.75,
            status=STATUS_PROPOSED,
            proposed_at=NOW,
        )
        await recommendation_store.save_recommendation(recommendation)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            # Lifecycle: status is the ONLY flippable column.
            await conn.execute(
                "UPDATE recommendations SET status = $1 WHERE id = $2",
                STATUS_ACCEPTED,
                recommendation.id,
            )
            # Content is immutable (P1): blocked by the trigger.
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE recommendations SET action_description = 'x' WHERE id = $1",
                    recommendation.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE recommendations SET confidence_score = 0.9 WHERE id = $1",
                    recommendation.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "DELETE FROM recommendations WHERE id = $1", recommendation.id
                )
        finally:
            await conn.close()
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_formulates_with_traceability_and_p1(
    recommendation_store,
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
):
    """End-to-end: understanding stream + calibrated confidence -> Recommendations."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx_id, evidence_id, anomaly, pattern_id = await _seed_traceability(
            tenant_id, context_store, evidence_store, anomaly_store, pattern_store
        )

        hypothesis_ids = []
        for description in (
            "Hipótesis candidata de saturación de disco.",
            "Hipótesis candidata de retención de logs.",
            "Hipótesis candidata de auto-growth.",
        ):
            create = HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=[anomaly.id],
                pattern_ids=[pattern_id],
                description=description,
                predicted_consequences=["El volumen persistido seguirá creciendo."],
                falsification_criterion="Si no se observa, se descarta.",
                coherence_score=0.5,
                status=STATUS_CANDIDATE,
            )
            hypothesis = build_hypothesis(create)
            await hypothesis_store.save_hypothesis(hypothesis)
            hypothesis_ids.append(hypothesis.id)
            # Calibrated Confidence for the hypothesis (Sprint 8, R4 gate).
            calibrated = build_confidence(
                make_confidence_create(tenant_id, hypothesis.id)
            )
            await confidence_store.save_confidence(calibrated)

        service = RecommendationService(
            hypothesis_store,
            anomaly_store,
            context_store,
            confidence_store,
            recommendation_store,
            action_space=ACTION_SPACE_LIBRARY,
        )
        proposed = await service.run_recommendation_cycle()
        assert proposed == len(hypothesis_ids)
        assert service.errors == 0
        assert service.total_hypotheses_without_confidence == 0

        conn = await asyncpg.connect(DSN_RAW)
        try:
            rows = await conn.fetch(
                "SELECT r.id, r.hypothesis_id, r.confidence_id, r.confidence_score,"
                "       r.status, r.action_description, r.rationale,"
                "       r.expected_consequences, r.alternatives_considered "
                "FROM recommendations r "
                "WHERE r.tenant_id = $1 "
                "ORDER BY r.proposed_at",
                tenant_id,
            )
            trace = await conn.fetch(
                "SELECT r.id AS recommendation_id, h.id AS hypothesis_id, "
                "       c.id AS confidence_id, a.id AS anomaly_id, "
                "       p.id AS pattern_id, ctx.id AS context_id, "
                "       e.id AS evidence_id, o.id AS observation_id "
                "FROM recommendations r "
                "JOIN hypotheses h ON h.id = r.hypothesis_id "
                "JOIN confidence_scores c ON c.id = r.confidence_id "
                "JOIN anomalies a ON a.id = ANY(h.anomaly_ids) "
                "JOIN patterns p ON p.id = a.pattern_id "
                "JOIN contexts ctx ON ctx.id = a.context_id "
                "JOIN evidence e ON e.id = ANY(ctx.evidence_ids) "
                "JOIN observations o ON o.id = ANY(e.observation_ids) "
                "WHERE r.tenant_id = $1",
                tenant_id,
            )
            unchanged = await conn.fetchrow(
                "SELECT (SELECT count(*) FROM observations WHERE tenant_id = $1) AS obs,"
                "       (SELECT count(*) FROM evidence WHERE tenant_id = $1) AS ev,"
                "       (SELECT count(*) FROM contexts WHERE tenant_id = $1) AS ctx,"
                "       (SELECT count(*) FROM patterns WHERE tenant_id = $1) AS pat,"
                "       (SELECT count(*) FROM anomalies WHERE tenant_id = $1) AS ano,"
                "       (SELECT count(*) FROM hypotheses WHERE tenant_id = $1) AS hyp,"
                "       (SELECT count(*) FROM confidence_scores WHERE tenant_id = $1) AS conf",
                tenant_id,
            )
        finally:
            await conn.close()

        assert len(rows) == len(hypothesis_ids)
        for row in rows:
            assert row["status"] == STATUS_PROPOSED  # advisory only
            assert row["confidence_id"] is not None  # R4: always calibrated
            assert 0.0 <= float(row["confidence_score"]) <= 1.0
            assert row["action_description"]
            assert row["rationale"]
            consequences = (
                row["expected_consequences"]
                if isinstance(row["expected_consequences"], list)
                else json.loads(row["expected_consequences"])
            )
            alternatives = (
                row["alternatives_considered"]
                if isinstance(row["alternatives_considered"], list)
                else json.loads(row["alternatives_considered"])
            )
            assert len(consequences) >= 1
            assert len(alternatives) >= 1
            for alternative in alternatives:
                assert alternative["rationale"]
                assert alternative["rejected_reason"]
                assert "confidence" in alternative

        # Full traceability: recommendation -> hypothesis -> confidence -> anomaly
        # -> pattern -> context -> evidence -> observations. (The 2 observations
        # multiply each row in the JOIN, so at least one per recommendation.)
        assert len(trace) >= len(hypothesis_ids)
        assert all(row["anomaly_id"] == anomaly.id for row in trace)
        assert all(row["pattern_id"] == pattern_id for row in trace)
        assert all(row["context_id"] == ctx_id for row in trace)
        assert all(row["evidence_id"] == evidence_id for row in trace)

        # Re-running the cycle must not duplicate rows (idempotent dedup).
        await service.run_recommendation_cycle()
        assert service.total_duplicates >= len(hypothesis_ids)
        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM recommendations WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == len(hypothesis_ids)

        # P1: perception + reasoning + learning artifacts untouched by Propose.
        assert unchanged["obs"] == 2
        assert unchanged["ev"] == 1
        assert unchanged["ctx"] == 1
        assert unchanged["pat"] == 1
        assert unchanged["ano"] == 1
        assert unchanged["hyp"] == len(hypothesis_ids)
        assert unchanged["conf"] == len(hypothesis_ids)
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_skips_hypotheses_without_confidence(
    recommendation_store,
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
):
    """R4: a hypothesis without calibrated Confidence yields NO recommendation."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        _, _, anomaly, pattern_id = await _seed_traceability(
            tenant_id, context_store, evidence_store, anomaly_store, pattern_store
        )
        for description in (
            "Hipótesis candidata de saturación de disco.",
            "Hipótesis candidata de retención de logs.",
        ):
            create = HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=[anomaly.id],
                pattern_ids=[pattern_id],
                description=description,
                predicted_consequences=["El volumen persistido seguirá creciendo."],
                falsification_criterion="Si no se observa, se descarta.",
                coherence_score=0.5,
                status=STATUS_CANDIDATE,
            )
            await hypothesis_store.save_hypothesis(build_hypothesis(create))

        # NO calibrated confidence is seeded -> the R4 gate must skip all.
        service = RecommendationService(
            hypothesis_store,
            anomaly_store,
            context_store,
            confidence_store,
            recommendation_store,
            action_space=ACTION_SPACE_LIBRARY,
        )
        proposed = await service.run_recommendation_cycle()
        assert proposed == 0
        assert service.total_hypotheses_without_confidence == 2
        assert service.errors == 0

        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM recommendations WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == 0
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_without_hypotheses_is_clean(recommendation_store):
    """No hypotheses -> zero recommendations and zero errors."""
    service = RecommendationService(
        HypothesisStore(DSN_STORE),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        recommendation_store,
        action_space=ACTION_SPACE_LIBRARY,
    )
    await service.hypothesis_store.verify_connection()
    proposed = await service.run_recommendation_cycle()
    assert proposed == 0
    assert service.errors == 0
    assert service.total_recommendations == 0
    await service.hypothesis_store.close()


def test_recommendation_service_metrics_are_exposed():
    service = RecommendationService.__new__(RecommendationService)
    service.total_recommendations = 3
    service.total_duplicates = 1
    service.total_hypotheses_without_confidence = 2
    service.total_hypotheses_without_context = 1
    service.total_hypotheses_without_action_space = 0
    service.errors = 0
    service.by_status = {"proposed": 3}
    service.by_domain = {"storage": 2, "backup": 1}
    service.last_run_at = None
    health = HealthServer(service)

    async def get_metrics():
        response = await health.metrics_handler(SimpleNamespace())
        body = json.loads(response.body)
        assert body["total_recommendations"] == 3
        assert body["total_recommendation_duplicates"] == 1
        assert body["total_hypotheses_without_confidence"] == 2
        assert body["total_errors"] == 0
        assert body["recommendations_by_status"] == {"proposed": 3}
        assert body["recommendations_by_domain"] == {"storage": 2, "backup": 1}

    asyncio.run(get_metrics())