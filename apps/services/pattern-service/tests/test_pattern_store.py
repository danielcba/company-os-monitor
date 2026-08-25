"""Integration tests for Pattern persistence, the detector service and traceability.

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
from libs.reasoning.pattern import (
    PatternCreate,
    PatternStore,
    build_pattern,
    pattern_id,
)

from src.health import HealthServer
from src.service import PatternService

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"pat-{tenant_id}",
            f"patslug-{tenant_id}",
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
    evidence_ids: list[uuid.UUID] | None = None,
) -> Context:
    return Context(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        evidence_ids=evidence_ids or [uuid.uuid4()],
        mental_model_id=model_id,
        purpose=purpose,
        coherence_score=0.7,
        competing_models=[
            {"mental_model_id": "resource_pressure", "coherence_score": 0.3},
            {"mental_model_id": model_id, "coherence_score": 0.7},
        ],
        activated_at=activated_at,
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
            NOW - timedelta(days=20),
            "Q1",
            '{"raw": true}',
        )
        return obs_id
    finally:
        await conn.close()


async def _seed_context_stream(tenant_id: uuid.UUID, context_store: ContextStore, evidence_ids) -> list[Context]:
    """Three capacity_risk/infrastructure_health activations, one week apart."""
    contexts = [
        make_context(tenant_id, "capacity_risk", "infrastructure_health", NOW - timedelta(days=14), evidence_ids),
        make_context(tenant_id, "capacity_risk", "infrastructure_health", NOW - timedelta(days=7), evidence_ids),
        make_context(tenant_id, "capacity_risk", "infrastructure_health", NOW, evidence_ids),
    ]
    for ctx in contexts:
        await context_store.save_context(ctx)
    return contexts


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


async def test_pattern_insert_and_read_back(pattern_store, context_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(tenant_id, "capacity_risk", "infrastructure_health", NOW)
        await context_store.save_context(ctx)

        create = PatternCreate(
            tenant_id=tenant_id,
            context_id=ctx.id,
            pattern_type="temporal",
            description="factual description",
            strength_measure=1.0,
            frequency="weekly",
            library_pattern_id="context_recurrence_capacity_risk_v1",
        )
        pattern = build_pattern(create)
        row = await pattern_store.save_pattern(pattern)
        assert row is not None
        assert row["id"] == pattern.id
        assert float(row["strength_measure"]) == pytest.approx(1.0)
        assert row["frequency"] == "weekly"
        assert row["pattern_type"] == "temporal"

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT description, strength_measure, frequency, context_id "
                "FROM patterns WHERE id = $1",
                pattern.id,
            )
        finally:
            await conn.close()
        assert selected["description"] == "factual description"
        assert float(selected["strength_measure"]) == pytest.approx(1.0)
        assert selected["frequency"] == "weekly"
        assert selected["context_id"] == ctx.id

        loaded = await pattern_store.list_patterns(tenant_id=tenant_id)
        assert [p.id for p in loaded] == [pattern.id]
        assert tenant_id in (await pattern_store.list_tenant_ids())
    finally:
        await _cleanup_tenant(tenant_id)


async def test_pattern_save_is_idempotent(pattern_store, context_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(tenant_id, "capacity_risk", "infrastructure_health", NOW)
        await context_store.save_context(ctx)
        create = PatternCreate(
            tenant_id=tenant_id,
            context_id=ctx.id,
            pattern_type="temporal",
            description="factual description",
            strength_measure=0.75,
            frequency="weekly",
            library_pattern_id="context_recurrence_capacity_risk_v1",
        )
        pattern = build_pattern(create)
        assert (await pattern_store.save_pattern(pattern)) is not None
        assert (await pattern_store.save_pattern(pattern)) is None
        assert await pattern_store.pattern_exists(id=pattern.id) is True
    finally:
        await _cleanup_tenant(tenant_id)


async def test_pattern_content_trigger_blocks_update_and_delete(pattern_store, context_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        ctx = make_context(tenant_id, "capacity_risk", "infrastructure_health", NOW)
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

        conn = await asyncpg.connect(DSN_RAW)
        try:
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE patterns SET description = 'retrofitted' WHERE id = $1",
                    pattern.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE patterns SET strength_measure = 0.1 WHERE id = $1",
                    pattern.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="never deleted"):
                await conn.execute("DELETE FROM patterns WHERE id = $1", pattern.id)
        finally:
            await conn.close()

        # Lifecycle flip is allowed (is_active is not content).
        conn = await asyncpg.connect(DSN_RAW)
        try:
            await conn.execute(
                "UPDATE patterns SET is_active = false WHERE id = $1", pattern.id
            )
            active = await conn.fetchval(
                "SELECT is_active FROM patterns WHERE id = $1", pattern.id
            )
        finally:
            await conn.close()
        assert active is False
    finally:
        await _cleanup_tenant(tenant_id)


async def test_context_store_reads_full_stream(context_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        first = make_context(tenant_id, "capacity_risk", "infrastructure_health", NOW - timedelta(days=10))
        second = make_context(tenant_id, "service_failure", "security_posture", NOW - timedelta(days=5))
        third = make_context(tenant_id, "capacity_risk", "capacity_management", NOW)
        for ctx in (first, second, third):
            await context_store.save_context(ctx)

        loaded = await context_store.list_contexts(tenant_id=tenant_id)
        assert [c.id for c in loaded] == [first.id, second.id, third.id]
        assert [c.activated_at for c in loaded] == sorted(
            c.activated_at for c in loaded
        )
        assert all(c.competing_models for c in loaded)

        # The stream keeps all activations even after a lifecycle flip.
        await context_store.set_active(
            id=first.id, tenant_id=tenant_id, is_active=False
        )
        loaded = await context_store.list_contexts(tenant_id=tenant_id)
        assert len(loaded) == 3
        assert tenant_id in (await context_store.list_tenant_ids())
    finally:
        await _cleanup_tenant(tenant_id)


async def test_pattern_service_detects_and_persists_with_traceability(
    context_store, pattern_store, evidence_store
):
    """End-to-end: contexts -> detector -> patterns with full traceability back to
    the observations, idempotent re-run, and no writes to perception tables."""
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
        await _seed_context_stream(tenant_id, context_store, [evidence.id])

        service = PatternService(context_store, pattern_store)
        detected = await service.run_detection_cycle()
        assert detected >= 1

        conn = await asyncpg.connect(DSN_RAW)
        try:
            rows = await conn.fetch(
                "SELECT p.id, p.context_id, p.strength_measure, p.frequency, p.description "
                "FROM patterns p WHERE p.tenant_id = $1",
                tenant_id,
            )
            trace = await conn.fetch(
                "SELECT p.id AS pattern_id, c.id AS context_id, "
                "       e.id AS evidence_id, o.id AS observation_id "
                "FROM patterns p "
                "JOIN contexts c ON c.id = p.context_id "
                "JOIN evidence e ON e.id = ANY(c.evidence_ids) "
                "JOIN observations o ON o.id = ANY(e.observation_ids) "
                "WHERE p.tenant_id = $1",
                tenant_id,
            )
        finally:
            await conn.close()

        assert len(rows) >= 1
        pattern_row = rows[0]
        assert float(pattern_row["strength_measure"]) == pytest.approx(1.0)
        assert pattern_row["frequency"] == "weekly"
        assert pattern_row["description"]
        assert not any(banned in pattern_row["description"].lower() for banned in ("porque", "fallará", "predice"))

        # Full traceability back to the observations (factual, no rule number):
        # pattern -> context -> evidence -> observations.
        assert len(trace) >= 1
        trace_ids = {row["observation_id"] for row in trace}
        assert trace_ids <= set(obs_ids)
        assert {row["evidence_id"] for row in trace} == {evidence.id}
        assert {row["context_id"] for row in trace} == {pattern_row["context_id"]}

        # Re-running the cycle must not duplicate patterns (idempotent dedup).
        await service.run_detection_cycle()
        assert service.total_duplicates >= 1
        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM patterns WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert count == len(rows)

        # P1: the perception tables are untouched by the Reasoning cycle.
        conn = await asyncpg.connect(DSN_RAW)
        try:
            unchanged = await conn.fetchrow(
                "SELECT (SELECT count(*) FROM observations WHERE tenant_id = $1) AS obs,"
                "       (SELECT count(*) FROM evidence WHERE tenant_id = $1) AS ev,"
                "       (SELECT count(*) FROM contexts WHERE tenant_id = $1) AS ctx",
                tenant_id,
            )
        finally:
            await conn.close()
        assert unchanged["obs"] == 2
        assert unchanged["ev"] == 1
        assert unchanged["ctx"] == 3
    finally:
        await _cleanup_tenant(tenant_id)


def test_pattern_service_metrics_are_exposed():
    service = SimpleNamespace(
        total_patterns=4,
        total_duplicates=1,
        total_below_threshold=2,
        errors=0,
        last_run_at=None,
        by_type={"temporal": 4},
        by_mental_model={"capacity_risk": 3, "service_failure": 1},
    )
    health = HealthServer(service)

    async def get_metrics():
        response = await health.metrics_handler(SimpleNamespace())
        body = json.loads(response.body)
        assert body["total_patterns"] == 4
        assert body["total_pattern_duplicates"] == 1
        assert body["total_candidates_below_threshold"] == 2
        assert body["total_errors"] == 0
        assert body["patterns_by_type"]["temporal"] == 4
        assert body["patterns_by_mental_model"]["capacity_risk"] == 3

    asyncio.run(get_metrics())


def test_pattern_id_namespace_is_distinct_from_context_evidence():
    tenant_id = uuid.uuid4()
    ctx_id = uuid.uuid4()
    library_pattern_id = "context_recurrence_capacity_risk_v1"
    pid = pattern_id(tenant_id, ctx_id, library_pattern_id)
    assert pid != ctx_id
