"""Integration tests for Anomaly persistence, the detector service and traceability.

Requires the sandbox infra (postgres at 127.0.0.1:5433). Cleanup disables the
P1/immutability triggers with session_replication_role = replica (superuser)
and deletes the child tables first (the content triggers + FK cascade over the
hypertable block plain DELETEs).
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
from libs.reasoning.anomaly import (
    AnomalyCreate,
    AnomalyStore,
    anomaly_id,
    build_anomaly,
)
from libs.reasoning.pattern import (
    PatternCreate,
    PatternStore,
    build_pattern,
    pattern_id,
)

from src.health import HealthServer
from src.service import AnomalyService

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"anom-{tenant_id}",
            f"anomslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    """Delete the test tenant and its cognitive rows (bypassing triggers)."""
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
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
    evidence_ids: list[uuid.UUID],
    *,
    is_active: bool = True,
) -> Context:
    return Context(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        evidence_ids=evidence_ids,
        mental_model_id=model_id,
        purpose=purpose,
        coherence_score=0.7,
        competing_models=[
            {"mental_model_id": "resource_pressure", "coherence_score": 0.3},
            {"mental_model_id": model_id, "coherence_score": 0.7},
        ],
        activated_at=activated_at,
        is_active=is_active,
    )


async def _seed_observation(tenant_id: uuid.UUID) -> uuid.UUID:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        obs_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO observations ("
            " id, tenant_id, source_id, source_type, fact_type, fact_value,"
            " unit, captured_at, quality_class, raw_payload)"
            " VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10::jsonb)",
            obs_id,
            tenant_id,
            uuid.uuid4(),
            "linux_agent",
            "backup_job_status",
            '{"status": "failed"}',
            "count",
            NOW - timedelta(days=10),
            "Q1",
            '{"raw": true}',
        )
        return obs_id
    finally:
        await conn.close()


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
async def anomaly_store():
    instance = AnomalyStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def evidence_store():
    instance = EvidenceStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


async def test_anomaly_insert_and_read_back(anomaly_store, context_store, pattern_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, [uuid.uuid4()]
        )
        await context_store.save_context(ctx)
        pattern = build_pattern(
            PatternCreate(
                tenant_id=tenant_id,
                context_id=ctx.id,
                pattern_type="temporal",
                description="factual description",
                strength_measure=1.0,
                frequency="weekly",
                library_pattern_id="context_recurrence_capacity_risk_v1",
            )
        )
        await pattern_store.save_pattern(pattern)

        create = AnomalyCreate(
            tenant_id=tenant_id,
            context_id=ctx.id,
            pattern_id=pattern.id,
            deviation_score=1.0,
            tolerance_threshold=0.5,
            anomaly_class="point",
        )
        anomaly = build_anomaly(create)
        row = await anomaly_store.save_anomaly(anomaly)
        assert row is not None
        assert row["id"] == anomaly.id
        assert float(row["deviation_score"]) == pytest.approx(1.0)
        assert float(row["tolerance_threshold"]) == pytest.approx(0.5)
        assert row["anomaly_class"] == "point"

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT deviation_score, tolerance_threshold, anomaly_class, "
                "       context_id, pattern_id FROM anomalies WHERE id = $1",
                anomaly.id,
            )
        finally:
            await conn.close()
        assert float(selected["deviation_score"]) == pytest.approx(1.0)
        assert float(selected["tolerance_threshold"]) == pytest.approx(0.5)
        assert selected["anomaly_class"] == "point"
        assert selected["context_id"] == ctx.id
        assert selected["pattern_id"] == pattern.id

        loaded = await anomaly_store.list_anomalies(tenant_id=tenant_id)
        assert [a.id for a in loaded] == [anomaly.id]
        assert tenant_id in (await anomaly_store.list_tenant_ids())
    finally:
        await _cleanup_tenant(tenant_id)


async def test_anomaly_save_is_idempotent(anomaly_store, context_store, pattern_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, [uuid.uuid4()]
        )
        await context_store.save_context(ctx)
        pattern = build_pattern(
            PatternCreate(
                tenant_id=tenant_id,
                context_id=ctx.id,
                pattern_type="temporal",
                description="factual description",
                strength_measure=1.0,
                frequency="weekly",
                library_pattern_id="context_recurrence_capacity_risk_v1",
            )
        )
        await pattern_store.save_pattern(pattern)

        anomaly = build_anomaly(
            AnomalyCreate(
                tenant_id=tenant_id,
                context_id=ctx.id,
                pattern_id=pattern.id,
                deviation_score=1.0,
                tolerance_threshold=0.5,
                anomaly_class="point",
            )
        )
        assert (await anomaly_store.save_anomaly(anomaly)) is not None
        assert (await anomaly_store.save_anomaly(anomaly)) is None
        assert await anomaly_store.anomaly_exists(id=anomaly.id) is True
    finally:
        await _cleanup_tenant(tenant_id)


async def test_anomaly_content_trigger_blocks_update_and_delete(
    anomaly_store, context_store, pattern_store
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, [uuid.uuid4()]
        )
        await context_store.save_context(ctx)
        pattern = build_pattern(
            PatternCreate(
                tenant_id=tenant_id,
                context_id=ctx.id,
                pattern_type="temporal",
                description="factual description",
                strength_measure=1.0,
                frequency="weekly",
                library_pattern_id="context_recurrence_capacity_risk_v1",
            )
        )
        await pattern_store.save_pattern(pattern)
        anomaly = build_anomaly(
            AnomalyCreate(
                tenant_id=tenant_id,
                context_id=ctx.id,
                pattern_id=pattern.id,
                deviation_score=1.0,
                tolerance_threshold=0.5,
                anomaly_class="point",
            )
        )
        await anomaly_store.save_anomaly(anomaly)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE anomalies SET deviation_score = 0.1 WHERE id = $1",
                    anomaly.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE anomalies SET tolerance_threshold = 0.9 WHERE id = $1",
                    anomaly.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute("DELETE FROM anomalies WHERE id = $1", anomaly.id)
        finally:
            await conn.close()
    finally:
        await _cleanup_tenant(tenant_id)


async def test_list_active_contexts_returns_only_active(context_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        evidence_ids = [uuid.uuid4()]
        anchor = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW - timedelta(days=7),
            evidence_ids,
        )
        active = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, evidence_ids
        )
        await context_store.save_context(anchor)
        await context_store.save_context(active)

        stream = await context_store.list_contexts(tenant_id=tenant_id)
        assert len(stream) == 2

        actives = await context_store.list_active_contexts(tenant_id=tenant_id)
        assert [c.id for c in actives] == [active.id]
        assert all(c.is_active for c in actives)
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_detects_persists_and_traces(
    context_store, pattern_store, anomaly_store, evidence_store
):
    """End-to-end: contexts + patterns -> detector -> anomalies with traceability
    back to the observations, idempotent re-run, and no writes to perception
    tables."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        obs_ids = [await _seed_observation(tenant_id), await _seed_observation(tenant_id)]
        evidence = build_evidence(
            EvidenceCreate(
                tenant_id=tenant_id,
                observation_ids=obs_ids,
                organization_type="backup_failure_evidence",
                description="factual organization",
                quality_class=QualityClass.Q1,
                weight=0.88,
            )
        )
        await evidence_store.save_evidence(evidence)

        anchor = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW - timedelta(days=7),
            [evidence.id],
        )
        active = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW + timedelta(days=14),
            [evidence.id],
        )
        await context_store.save_context(anchor)
        await context_store.save_context(active)

        # Self-contained isolation: the detection cycle scans ALL tenants (it is
        # not scoped to one), so total_contexts_without_pattern also reflects the
        # shared sandbox tenant. Seed active contexts with NO matching pattern for
        # THIS tenant so the metric is deterministic and does not depend on the
        # sandbox tenant's accumulated state (test isolation, Phase B). These
        # contexts increment contexts_without_pattern but never become anomalies
        # (a context lacking a pattern is counted, not emitted).
        for i, purpose in enumerate(
            ("security_posture", "backup_health", "network_health")
        ):
            orphan = make_context(
                tenant_id,
                "capacity_risk",
                purpose,
                NOW + timedelta(days=14 + i),
                [evidence.id],
            )
            await context_store.save_context(orphan)

        pattern = build_pattern(
            PatternCreate(
                tenant_id=tenant_id,
                context_id=anchor.id,
                pattern_type="temporal",
                description="Recurrencia semanal del contexto capacity_risk para infrastructure_health. Regularidad detectada.",
                strength_measure=1.0,
                frequency="weekly",
                library_pattern_id="context_recurrence_capacity_risk_v1",
                detected_at=NOW - timedelta(days=7),
            )
        )
        await pattern_store.save_pattern(pattern)

        service = AnomalyService(context_store, pattern_store, anomaly_store)
        detected = await service.run_detection_cycle()
        assert detected == 1
        assert service.total_anomalies == 1
        # The sandbox tenant (3 active contexts, 0 patterns) is part of the
        # same cycle and contributes to this metric - the documented real-data
        # scenario where no expected pattern means no anomaly.
        assert service.total_contexts_without_pattern >= 3

        conn = await asyncpg.connect(DSN_RAW)
        try:
            rows = await conn.fetch(
                "SELECT id, context_id, pattern_id, deviation_score, "
                "       tolerance_threshold, anomaly_class "
                "FROM anomalies WHERE tenant_id = $1",
                tenant_id,
            )
            trace = await conn.fetch(
                "SELECT a.id AS anomaly_id, a.context_id AS anomaly_context_id, "
                "       p.id AS pattern_id, c.id AS anchor_context_id, "
                "       e.id AS evidence_id, o.id AS observation_id "
                "FROM anomalies a "
                "JOIN patterns p ON p.id = a.pattern_id "
                "JOIN contexts c ON c.id = p.context_id "
                "JOIN evidence e ON e.id = ANY(c.evidence_ids) "
                "JOIN observations o ON o.id = ANY(e.observation_ids) "
                "WHERE a.tenant_id = $1",
                tenant_id,
            )
        finally:
            await conn.close()

        assert len(rows) == 1
        row = rows[0]
        assert float(row["deviation_score"]) == pytest.approx(2.0)
        assert float(row["tolerance_threshold"]) == pytest.approx(0.5)
        assert row["anomaly_class"] == "point"
        assert row["context_id"] == active.id
        assert row["pattern_id"] == pattern.id

        # Traceability: anomaly -> pattern -> anchor context -> evidence -> observations.
        # Two observation rows (the evidence organizes both), all tracing to
        # the same anomaly/pattern/context/evidence chain.
        assert len(trace) == 2
        assert {row["anomaly_id"] for row in trace} == {row["id"]}
        assert {row["pattern_id"] for row in trace} == {pattern.id}
        assert {row["anchor_context_id"] for row in trace} == {anchor.id}
        assert {row["evidence_id"] for row in trace} == {evidence.id}
        assert {row["observation_id"] for row in trace} == set(obs_ids)

        # Re-running the cycle must not duplicate anomalies (idempotent dedup).
        await service.run_detection_cycle()
        assert service.total_duplicates >= 1
        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM anomalies WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == 1

        # P1: the perception + pattern tables are untouched by the anomaly cycle.
        conn = await asyncpg.connect(DSN_RAW)
        try:
            unchanged = await conn.fetchrow(
                "SELECT (SELECT count(*) FROM observations WHERE tenant_id = $1) AS obs,"
                "       (SELECT count(*) FROM evidence WHERE tenant_id = $1) AS ev,"
                "       (SELECT count(*) FROM contexts WHERE tenant_id = $1) AS ctx,"
                "       (SELECT count(*) FROM patterns WHERE tenant_id = $1) AS pat",
                tenant_id,
            )
        finally:
            await conn.close()
        assert unchanged["obs"] == 2
        assert unchanged["ev"] == 1
        # 2 seeded contexts (anchor + active) + 3 orphan contexts without a
        # matching pattern; the anomaly cycle must not add or remove any context.
        assert unchanged["ctx"] == 5
        assert unchanged["pat"] == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_without_patterns_emits_no_anomalies(
    context_store, pattern_store, anomaly_store
):
    """Without an expected Pattern there is NO anomaly (relative to patterns,
    never absolute) - only the contexts_without_pattern metric."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        evidence_ids = [uuid.uuid4()]
        for model_id, purpose in (
            ("capacity_risk", "infrastructure_health"),
            ("service_failure", "security_posture"),
        ):
            await context_store.save_context(
                make_context(tenant_id, model_id, purpose, NOW, evidence_ids)
            )

        service = AnomalyService(context_store, pattern_store, anomaly_store)
        detected = await service.run_detection_cycle()
        assert detected == 0
        assert service.total_anomalies == 0
        # At least our two active contexts have no expected pattern; the
        # sandbox tenant (3 active contexts, 0 patterns) adds to the same
        # metric on this shared cycle.
        assert service.total_contexts_without_pattern >= 2

        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM anomalies WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == 0
    finally:
        await _cleanup_tenant(tenant_id)


def test_anomaly_id_is_deterministic_and_distinct_namespace():
    tenant_id = uuid.uuid4()
    ctx_id = uuid.uuid4()
    pattern = pattern_id(
        tenant_id, ctx_id, "context_recurrence_capacity_risk_v1"
    )
    a = anomaly_id(tenant_id, ctx_id, pattern)
    assert a == anomaly_id(tenant_id, ctx_id, pattern)
    assert a != ctx_id
    assert a != pattern
    assert a != anomaly_id(tenant_id, ctx_id, uuid.uuid4())


def test_build_anomaly_produces_same_id_for_same_facts():
    tenant_id = uuid.uuid4()
    ctx_id = uuid.uuid4()
    pattern = uuid.uuid4()
    facts = {
        "tenant_id": tenant_id,
        "context_id": ctx_id,
        "pattern_id": pattern,
        "deviation_score": 2.0,
        "tolerance_threshold": 0.5,
        "anomaly_class": "point",
    }
    first = build_anomaly(AnomalyCreate(**facts))
    second = build_anomaly(AnomalyCreate(**facts))
    assert first.id == second.id
    assert first.tenant_id == tenant_id
    assert first.context_id == ctx_id
    assert first.pattern_id == pattern
    assert first.deviation_score == 2.0
    assert first.tolerance_threshold == 0.5


def test_anomaly_service_metrics_are_exposed():
    service = SimpleNamespace(
        total_anomalies=3,
        total_duplicates=1,
        total_contexts_without_pattern=2,
        total_contexts_without_tolerance=4,
        errors=0,
        last_run_at=None,
        by_class={"point": 3},
        by_mental_model={"capacity_risk": 2, "service_failure": 1},
    )
    health = HealthServer(service)

    async def get_metrics():
        response = await health.metrics_handler(SimpleNamespace())
        body = json.loads(response.body)
        assert body["total_anomalies"] == 3
        assert body["total_anomaly_duplicates"] == 1
        assert body["total_contexts_without_pattern"] == 2
        assert body["total_contexts_without_tolerance"] == 4
        assert body["total_errors"] == 0
        assert body["anomalies_by_class"]["point"] == 3
        assert body["anomalies_by_mental_model"]["capacity_risk"] == 2

    asyncio.run(get_metrics())


# ===========================================================================
# Regression tests for Context Activation atomicity (idx_contexts_unique_active)
# ===========================================================================


async def test_case_a_save_active_without_prior_active(context_store):
    """Caso A: saving an active context when none exists becomes the active one."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, [uuid.uuid4()]
        )
        await context_store.save_context(ctx)
        actives = await context_store.list_active_contexts(tenant_id=tenant_id)
        assert [c.id for c in actives] == [ctx.id]
        assert all(c.is_active for c in actives)
        stream = await context_store.list_contexts(tenant_id=tenant_id)
        assert len(stream) == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_case_b_save_active_replaces_previous_active(context_store):
    """Caso B: a new active context supersedes the previous active one."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        evidence_ids = [uuid.uuid4()]
        anchor = make_context(
            tenant_id, "capacity_risk", "infrastructure_health",
            NOW - timedelta(days=7), evidence_ids,
        )
        active = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, evidence_ids
        )
        await context_store.save_context(anchor)
        await context_store.save_context(active)

        stream = await context_store.list_contexts(tenant_id=tenant_id)
        assert len(stream) == 2
        actives = await context_store.list_active_contexts(tenant_id=tenant_id)
        assert [c.id for c in actives] == [active.id]
        assert all(c.is_active for c in actives)
    finally:
        await _cleanup_tenant(tenant_id)


async def test_case_c_save_inactive_does_not_deactivate_active(context_store):
    """Caso C: saving an INACTIVE (historical) context must NOT tear down the
    currently active context of the same tenant+purpose."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        evidence_ids = [uuid.uuid4()]
        anchor = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, evidence_ids
        )
        historical = make_context(
            tenant_id, "capacity_risk", "infrastructure_health",
            NOW - timedelta(days=30), evidence_ids, is_active=False,
        )
        await context_store.save_context(anchor)
        await context_store.save_context(historical)

        stream = await context_store.list_contexts(tenant_id=tenant_id)
        assert len(stream) == 2
        actives = await context_store.list_active_contexts(tenant_id=tenant_id)
        assert [c.id for c in actives] == [anchor.id]
    finally:
        await _cleanup_tenant(tenant_id)


async def test_case_d_save_same_context_twice_is_idempotent(context_store):
    """Caso D: saving the same context twice does not duplicate or flip state."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, [uuid.uuid4()]
        )
        assert await context_store.save_context(ctx) is not None
        assert await context_store.save_context(ctx) is None
        stream = await context_store.list_contexts(tenant_id=tenant_id)
        assert len(stream) == 1
        actives = await context_store.list_active_contexts(tenant_id=tenant_id)
        assert [c.id for c in actives] == [ctx.id]
    finally:
        await _cleanup_tenant(tenant_id)


async def test_case_e_two_active_same_tenant_purpose_leaves_one(context_store):
    """Caso E: activating two different contexts for the same tenant+purpose
    must never leave two active rows (partial UNIQUE index respected)."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        a = make_context(
            tenant_id, "capacity_risk", "infrastructure_health",
            NOW - timedelta(days=1), [uuid.uuid4()],
        )
        b = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, [uuid.uuid4()]
        )
        await context_store.save_context(a)
        await context_store.save_context(b)
        actives = await context_store.list_active_contexts(tenant_id=tenant_id)
        assert len(actives) == 1
        assert actives[0].id == b.id
    finally:
        await _cleanup_tenant(tenant_id)


async def test_case_f_two_tenants_same_purpose_are_independent(context_store):
    """Caso F: tenant A + purpose X is fully independent of tenant B + purpose X."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _create_tenant(tenant_a)
    await _create_tenant(tenant_b)
    try:
        ctx_a = make_context(
            tenant_a, "capacity_risk", "infrastructure_health", NOW, [uuid.uuid4()]
        )
        ctx_b = make_context(
            tenant_b, "capacity_risk", "infrastructure_health", NOW, [uuid.uuid4()]
        )
        await context_store.save_context(ctx_a)
        await context_store.save_context(ctx_b)
        actives_a = await context_store.list_active_contexts(tenant_id=tenant_a)
        actives_b = await context_store.list_active_contexts(tenant_id=tenant_b)
        assert [c.id for c in actives_a] == [ctx_a.id]
        assert [c.id for c in actives_b] == [ctx_b.id]
    finally:
        await _cleanup_tenant(tenant_a)
        await _cleanup_tenant(tenant_b)


async def test_case_g_concurrent_activations_leave_one_active(context_store):
    """Caso G: concurrent activations for the same tenant+purpose must never
    produce two active rows (advisory lock serializes the transition)."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        contexts = [
            make_context(
                tenant_id, "capacity_risk", "infrastructure_health",
                NOW + timedelta(minutes=i), [uuid.uuid4()],
            )
            for i in range(5)
        ]

        async def _save(c):
            return await context_store.save_context(c)

        results = await asyncio.gather(*[_save(c) for c in contexts])
        # At least one activation succeeded; the partial UNIQUE index +
        # advisory lock guarantee at most one active context.
        assert any(r is not None for r in results)
        actives = await context_store.list_active_contexts(tenant_id=tenant_id)
        assert len(actives) == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_case_h_rollback_keeps_prior_active_on_failure(context_store):
    """Caso H: if the activation transition fails mid-way (after the prior
    active context was deactivated), the transaction rolls back and the prior
    active context remains the sole active one (no 0-active state)."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        anchor = make_context(
            tenant_id, "capacity_risk", "infrastructure_health", NOW, [uuid.uuid4()]
        )
        await context_store.save_context(anchor)

        # Wrap the session factory so the INSERT step raises, forcing a rollback
        # of the deactivation that preceded it.
        real_factory = context_store._session_factory

        class _FailingSession:
            def __init__(self, real):
                self._real = real

            async def __aenter__(self):
                self._sess = await self._real().__aenter__()
                self._orig = self._sess.execute

                async def failing(stmt, params=None, **kw):
                    if "INSERT INTO contexts" in str(stmt):
                        raise RuntimeError("injected insert failure")
                    return await self._orig(stmt, params, **kw)

                self._sess.execute = failing
                return self._sess

            async def __aexit__(self, *exc):
                return await self._real().__aexit__(*exc)

        class _FailingFactory:
            def __init__(self, real):
                self._real = real

            def __call__(self):
                return _FailingSession(self._real)

        context_store._session_factory = _FailingFactory(real_factory)

        broken = make_context(
            tenant_id, "capacity_risk", "infrastructure_health",
            NOW + timedelta(days=1), [uuid.uuid4()],
        )
        with pytest.raises(RuntimeError):
            await context_store.save_context(broken)

        # Restore the real factory before asserting DB state.
        context_store._session_factory = real_factory
        actives = await context_store.list_active_contexts(tenant_id=tenant_id)
        assert [c.id for c in actives] == [anchor.id]
    finally:
        context_store._session_factory = context_store._session_factory
        await _cleanup_tenant(tenant_id)