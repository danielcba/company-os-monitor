"""Integration tests for Hypothesis persistence, the generator service and traceability.

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

from src.generator import generate
from src.health import HealthServer
from src.service import HypothesisService

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
            f"hyp-{tenant_id}",
            f"hypslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
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
    tenant_id: uuid.UUID,
    model_id: str,
    purpose: str,
    activated_at: datetime,
) -> Context:
    return Context(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        evidence_ids=[uuid.uuid4()],
        mental_model_id=model_id,
        purpose=purpose,
        coherence_score=0.7,
        competing_models=[],
        activated_at=activated_at,
    )


def make_anomaly(
    tenant_id: uuid.UUID,
    ctx_id: uuid.UUID,
    pattern_id: uuid.UUID,
) -> Anomaly:
    return Anomaly(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        context_id=ctx_id,
        pattern_id=pattern_id,
        deviation_score=2.5,
        tolerance_threshold=1.0,
        anomaly_class="point",
        detected_at=NOW,
    )


def make_pattern(
    tenant_id: uuid.UUID,
    ctx_id: uuid.UUID,
    pattern_id: uuid.UUID,
) -> Pattern:
    return Pattern(
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


async def _seed_traceability(
    tenant_id: uuid.UUID,
    context_store: ContextStore,
    evidence_store: EvidenceStore,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed observation -> evidence -> context (the back-chain of a hypothesis)."""
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
            organization_type="disk_saturation_evidence",
            description="factual organization",
            quality_class=QualityClass.Q1,
            weight=0.88,
        )
    )
    await evidence_store.save_evidence(evidence)

    ctx = make_context(tenant_id, "resource_pressure", "infrastructure_health", NOW)
    ctx = ctx.model_copy(update={"evidence_ids": [evidence.id]})
    await context_store.save_context(ctx)
    return ctx.id, evidence.id


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
async def pattern_store():
    instance = PatternStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def evidence_store():
    instance = EvidenceStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


async def test_hypothesis_insert_and_read_back(hypothesis_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        anomaly_id = uuid.uuid4()
        create = HypothesisCreate(
            tenant_id=tenant_id,
            anomaly_ids=[anomaly_id],
            pattern_ids=[],
            description="Una hipótesis candidata.",
            predicted_consequences=["Consecuencia observable."],
            falsification_criterion="Si la consecuencia no se observa, se descarta.",
            coherence_score=0.5,
            status=STATUS_CANDIDATE,
        )
        hypothesis = build_hypothesis(create)
        row = await hypothesis_store.save_hypothesis(hypothesis)
        assert row is not None
        assert row["id"] == hypothesis.id
        assert row["status"] == STATUS_CANDIDATE
        assert row["falsification_criterion"].startswith("Si la consecuencia")

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT description, falsification_criterion, status, "
                "       anomaly_ids, predicted_consequences "
                "FROM hypotheses WHERE id = $1",
                hypothesis.id,
            )
        finally:
            await conn.close()
        assert selected["description"] == "Una hipótesis candidata."
        assert selected["status"] == STATUS_CANDIDATE
        assert anomaly_id in selected["anomaly_ids"]
        assert json.loads(selected["predicted_consequences"]) == ["Consecuencia observable."]

        loaded = await hypothesis_store.list_hypotheses(tenant_id=tenant_id)
        assert [h.id for h in loaded] == [hypothesis.id]
        assert tenant_id in (await hypothesis_store.list_tenant_ids())
    finally:
        await _cleanup_tenant(tenant_id)


async def test_hypothesis_save_is_idempotent(hypothesis_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        create = HypothesisCreate(
            tenant_id=tenant_id,
            anomaly_ids=[uuid.uuid4()],
            pattern_ids=[],
            description="Hipótesis idempotente.",
            predicted_consequences=["Consecuencia."],
            falsification_criterion="Criterio de falsificación.",
            coherence_score=0.5,
            status=STATUS_CANDIDATE,
        )
        hypothesis = build_hypothesis(create)
        assert (await hypothesis_store.save_hypothesis(hypothesis)) is not None
        assert (await hypothesis_store.save_hypothesis(hypothesis)) is None
        assert await hypothesis_store.hypothesis_exists(id=hypothesis.id) is True
    finally:
        await _cleanup_tenant(tenant_id)


async def test_hypothesis_content_trigger_allows_only_status_flip(hypothesis_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        create = HypothesisCreate(
            tenant_id=tenant_id,
            anomaly_ids=[uuid.uuid4()],
            pattern_ids=[],
            description="Hipótesis inmutable.",
            predicted_consequences=["Consecuencia."],
            falsification_criterion="Criterio.",
            coherence_score=0.5,
            status=STATUS_CANDIDATE,
        )
        hypothesis = build_hypothesis(create)
        await hypothesis_store.save_hypothesis(hypothesis)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE hypotheses SET description = 'retrofitted' WHERE id = $1",
                    hypothesis.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE hypotheses SET coherence_score = 0.9 WHERE id = $1",
                    hypothesis.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute("DELETE FROM hypotheses WHERE id = $1", hypothesis.id)

            # Status lifecycle flip is the ONLY allowed mutation.
            await conn.execute(
                "UPDATE hypotheses SET status = 'falsified' WHERE id = $1",
                hypothesis.id,
            )
            status = await conn.fetchval(
                "SELECT status FROM hypotheses WHERE id = $1", hypothesis.id
            )
        finally:
            await conn.close()
        assert status == "falsified"
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_generates_and_persists_with_traceability(
    context_store, evidence_store, anomaly_store, pattern_store, hypothesis_store
):
    """End-to-end: anomaly -> generator -> hypotheses with back-chain to observations."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx_id, _evidence_id = await _seed_traceability(tenant_id, context_store, evidence_store)
        pattern_id = uuid.uuid4()
        pattern = make_pattern(tenant_id, ctx_id, pattern_id)
        await pattern_store.save_pattern(pattern)
        anomaly = make_anomaly(tenant_id, ctx_id, pattern_id)
        await anomaly_store.save_anomaly(anomaly)

        service = HypothesisService(
            anomaly_store, context_store, pattern_store, hypothesis_store
        )
        generated = await service.run_generation_cycle()
        assert generated >= 2

        conn = await asyncpg.connect(DSN_RAW)
        try:
            rows = await conn.fetch(
                "SELECT id, status, anomaly_ids, description "
                "FROM hypotheses WHERE tenant_id = $1",
                tenant_id,
            )
            trace = await conn.fetch(
                "SELECT h.id AS hypothesis_id, a.id AS anomaly_id, "
                "       p.id AS pattern_id, c.id AS context_id, "
                "       e.id AS evidence_id, o.id AS observation_id "
                "FROM hypotheses h "
                "JOIN anomalies a ON a.id = ANY(h.anomaly_ids) "
                "JOIN patterns p ON p.id = a.pattern_id "
                "JOIN contexts c ON c.id = a.context_id "
                "JOIN evidence e ON e.id = ANY(c.evidence_ids) "
                "JOIN observations o ON o.id = ANY(e.observation_ids) "
                "WHERE h.tenant_id = $1",
                tenant_id,
            )
        finally:
            await conn.close()

        assert len(rows) >= 2, "competing hypotheses (no premature convergence)"
        assert all(row["status"] == STATUS_CANDIDATE for row in rows)
        assert all(row["description"] for row in rows)
        assert all(anomaly.id in row["anomaly_ids"] for row in rows)

        # Traceability: hypothesis -> anomaly -> pattern -> context -> evidence -> observations.
        assert len(trace) >= 2
        assert all(row["anomaly_id"] == anomaly.id for row in trace)
        assert all(row["pattern_id"] == pattern_id for row in trace)

        # Re-running the cycle must not duplicate hypotheses (idempotent dedup).
        await service.run_generation_cycle()
        assert service.total_duplicates >= 1
        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM hypotheses WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == len(rows)

        # P1: perception + reasoning tables are untouched by the hypothesis cycle.
        conn = await asyncpg.connect(DSN_RAW)
        try:
            unchanged = await conn.fetchrow(
                "SELECT (SELECT count(*) FROM observations WHERE tenant_id = $1) AS obs,"
                "       (SELECT count(*) FROM evidence WHERE tenant_id = $1) AS ev,"
                "       (SELECT count(*) FROM contexts WHERE tenant_id = $1) AS ctx,"
                "       (SELECT count(*) FROM patterns WHERE tenant_id = $1) AS pat,"
                "       (SELECT count(*) FROM anomalies WHERE tenant_id = $1) AS ano",
                tenant_id,
            )
        finally:
            await conn.close()
        assert unchanged["obs"] == 2
        assert unchanged["ev"] == 1
        assert unchanged["ctx"] == 1
        assert unchanged["pat"] == 1
        assert unchanged["ano"] == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_counts_anomalies_without_templates(
    context_store, anomaly_store, pattern_store, hypothesis_store
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(tenant_id, "service_failure", "security_posture", NOW)
        await context_store.save_context(ctx)
        pattern_id = uuid.uuid4()
        pattern = make_pattern(tenant_id, ctx.id, pattern_id)
        await pattern_store.save_pattern(pattern)
        anomaly = make_anomaly(tenant_id, ctx.id, pattern_id)
        await anomaly_store.save_anomaly(anomaly)

        service = HypothesisService(
            anomaly_store, context_store, pattern_store, hypothesis_store
        )
        generated = await service.run_generation_cycle()
        assert generated == 0
        assert service.total_anomalies_no_templates == 1

        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM hypotheses WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == 0
    finally:
        await _cleanup_tenant(tenant_id)


def test_hypothesis_service_metrics_are_exposed():
    service = SimpleNamespace(
        total_hypotheses=4,
        total_duplicates=1,
        total_anomalies_no_templates=2,
        errors=0,
        last_run_at=None,
        by_status={"candidate": 4},
        by_mental_model={"resource_pressure": 3, "capacity_risk": 1},
    )
    health = HealthServer(service)

    async def get_metrics():
        response = await health.metrics_handler(SimpleNamespace())
        body = json.loads(response.body)
        assert body["total_hypotheses"] == 4
        assert body["total_hypothesis_duplicates"] == 1
        assert body["total_anomalies_no_templates"] == 2
        assert body["total_errors"] == 0
        assert body["hypotheses_by_status"]["candidate"] == 4
        assert body["hypotheses_by_mental_model"]["resource_pressure"] == 3

    asyncio.run(get_metrics())


async def test_generator_used_by_service_resolves_scope_from_context(context_store):
    """The generator resolves the anomaly scope through the Active Context."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(tenant_id, "capacity_risk", "infrastructure_health", NOW)
        await context_store.save_context(ctx)
        anomaly = make_anomaly(tenant_id, ctx.id, uuid.uuid4())
        contexts = await context_store.list_contexts(tenant_id=tenant_id)
        creations = generate(anomaly, contexts, [])
        assert len(creations) >= 2
        assert all("capacity_risk" in c.description for c in creations)
    finally:
        await _cleanup_tenant(tenant_id)