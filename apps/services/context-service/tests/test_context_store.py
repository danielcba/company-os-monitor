"""Integration tests for Context persistence and the Context Activator service.

Requires the sandbox infra (postgres at 127.0.0.1:5433). Cleanup disables the
P1/immutability triggers with session_replication_role = replica (superuser)
and deletes the child tables first (the content trigger blocks plain DELETEs).
"""
import asyncio
import json
import uuid
from types import SimpleNamespace

import asyncpg
import pytest
from aiohttp import web
from libs.perception.context import (
    PURPOSES,
    Context,
    ContextCreate,
    ContextStore,
    build_context,
)
from libs.perception.evidence import EvidenceStore, build_evidence
from libs.perception.observation import EvidenceCreate, QualityClass

from src.activator import ActivatorEngine
from src.health import HealthServer
from src.service import ContextService

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"ctx-{tenant_id}",
            f"ctxslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    """Delete the test tenant and its contexts/evidence (bypassing triggers)."""
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
    evidence_ids: list[uuid.UUID],
    purpose: str,
    model_id: str = "capacity_risk",
    score: float = 0.66,
) -> Context:
    return build_context(
        ContextCreate(
            tenant_id=tenant_id,
            evidence_ids=evidence_ids,
            mental_model_id=model_id,
            purpose=purpose,
            coherence_score=score,
            competing_models=[
                {"mental_model_id": "resource_pressure", "coherence_score": 0.33},
                {"mental_model_id": model_id, "coherence_score": score},
            ],
        )
    )


def make_evidence(tenant_id: uuid.UUID, org_type: str):
    create = EvidenceCreate(
        tenant_id=tenant_id,
        observation_ids=[uuid.uuid4(), uuid.uuid4()],
        organization_type=org_type,
        description="factual organization",
        quality_class=QualityClass.Q1,
        weight=0.88,
    )
    return build_evidence(create)


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


async def test_save_context_and_read_back(context_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        evidence_ids = [uuid.uuid4(), uuid.uuid4()]
        context = make_context(tenant_id, evidence_ids, "infrastructure_health")
        row = await context_store.save_context(context)
        assert row["id"] == context.id
        assert row["mental_model_id"] == "capacity_risk"
        assert float(row["coherence_score"]) == pytest.approx(0.66)
        assert row["is_active"] is True

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT evidence_ids, competing_models, purpose, coherence_score "
                "FROM contexts WHERE id = $1",
                context.id,
            )
        finally:
            await conn.close()
        assert selected["evidence_ids"] == evidence_ids
        assert selected["purpose"] == "infrastructure_health"
        assert float(selected["coherence_score"]) == pytest.approx(0.66)
        competing = json.loads(selected["competing_models"])
        assert competing[0]["mental_model_id"] == "resource_pressure"
        assert competing[1]["coherence_score"] == pytest.approx(0.66)
    finally:
        await _cleanup_tenant(tenant_id)


async def test_context_save_is_idempotent(context_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        context = make_context(tenant_id, [uuid.uuid4()], "capacity_management")
        assert (await context_store.save_context(context)) is not None
        assert (await context_store.save_context(context)) is None
        assert await context_store.context_exists(id=context.id) is True

        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM contexts WHERE id = $1", context.id
            )
        finally:
            await conn.close()
        assert count == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_new_activation_supersedes_previous_active_context(context_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        first = make_context(
            tenant_id,
            [uuid.uuid4(), uuid.uuid4()],
            "infrastructure_health",
            "resource_pressure",
            0.5,
        )
        assert (await context_store.save_context(first)) is not None

        second = make_context(
            tenant_id, [uuid.uuid4()], "infrastructure_health", "capacity_risk", 0.8
        )
        assert (await context_store.save_context(second)) is not None

        conn = await asyncpg.connect(DSN_RAW)
        try:
            first_active = await conn.fetchval(
                "SELECT is_active FROM contexts WHERE id = $1", first.id
            )
            second_active = await conn.fetchval(
                "SELECT is_active FROM contexts WHERE id = $1", second.id
            )
        finally:
            await conn.close()
        assert first_active is False
        assert second_active is True
    finally:
        await _cleanup_tenant(tenant_id)


async def test_superseding_ids_only_flips_is_active_without_duplicate_deactivation(
    context_store,
):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        context = make_context(tenant_id, [uuid.uuid4()], "security_posture")
        assert (await context_store.save_context(context)) is not None
        # Re-running the same activation is a dedup: the active row stays active.
        assert (await context_store.save_context(context)) is None
        conn = await asyncpg.connect(DSN_RAW)
        try:
            active = await conn.fetchval(
                "SELECT is_active FROM contexts WHERE id = $1", context.id
            )
        finally:
            await conn.close()
        assert active is True
    finally:
        await _cleanup_tenant(tenant_id)


async def test_context_content_trigger_blocks_content_update_and_delete(context_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        context = make_context(tenant_id, [uuid.uuid4()], "infrastructure_health")
        await context_store.save_context(context)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE contexts SET mental_model_id = 'auth_compromise' WHERE id = $1",
                    context.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE contexts SET coherence_score = 0.99 WHERE id = $1",
                    context.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="never deleted"):
                await conn.execute("DELETE FROM contexts WHERE id = $1", context.id)
        finally:
            await conn.close()

        # Lifecycle flip is allowed (is_active is not content).
        await context_store.set_active(
            id=context.id, tenant_id=tenant_id, is_active=False
        )
        conn = await asyncpg.connect(DSN_RAW)
        try:
            active = await conn.fetchval(
                "SELECT is_active FROM contexts WHERE id = $1", context.id
            )
        finally:
            await conn.close()
        assert active is False
    finally:
        await _cleanup_tenant(tenant_id)


async def test_context_service_activates_real_evidence_end_to_end(context_store, evidence_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        persisted_evidence = []
        for org_type in (
            "resource_exhaustion_evidence",
            "service_degradation_evidence",
            "backup_failure_evidence",
        ):
            evidence = make_evidence(tenant_id, org_type)
            await evidence_store.save_evidence(evidence)
            persisted_evidence.append(evidence)

        service = ContextService(evidence_store, context_store, engine=ActivatorEngine())
        activated = await service.run_activation_cycle()
        assert activated >= 1

        conn = await asyncpg.connect(DSN_RAW)
        try:
            rows = await conn.fetch(
                "SELECT evidence_ids, mental_model_id, coherence_score, "
                "competing_models, is_active FROM contexts WHERE tenant_id = $1",
                tenant_id,
            )
        finally:
            await conn.close()
        real_ids = {e.id for e in persisted_evidence}
        assert len(rows) == len(list(PURPOSES))
        for row in rows:
            assert set(row["evidence_ids"]) <= real_ids
            assert row["mental_model_id"]
            assert row["coherence_score"] is not None
            competing = json.loads(row["competing_models"])
            assert len(competing) >= 2
            assert row["is_active"] is True

        # Re-running the cycle must not duplicate contexts (idempotent dedup).
        before = len(rows)
        await service.run_activation_cycle()
        conn = await asyncpg.connect(DSN_RAW)
        try:
            after_count = await conn.fetchval(
                "SELECT count(*) FROM contexts WHERE tenant_id = $1", tenant_id
            )
        finally:
            await conn.close()
        assert after_count == before
    finally:
        await _cleanup_tenant(tenant_id)


def test_context_service_metrics_are_exposed():
    service = SimpleNamespace(
        contexts_activated=5,
        contexts_duplicates=2,
        errors=0,
        last_run_at=None,
        by_mental_model={"capacity_risk": 3, "resource_pressure": 2},
        by_purpose={"infrastructure_health": 4, "capacity_management": 1},
    )
    health = HealthServer(service)

    async def get_metrics():
        response = await health.metrics_handler(SimpleNamespace())
        body = json.loads(response.body)
        assert body["total_contexts"] == 5
        assert body["total_errors"] == 0
        assert body["contexts_by_mental_model"]["capacity_risk"] == 3
        assert body["contexts_by_purpose"]["infrastructure_health"] == 4
        assert isinstance(response, web.Response)

    asyncio.run(get_metrics())