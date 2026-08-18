"""Integration tests for EvidenceStore against the running Postgres database.

Requires the sandbox infra (postgres at 127.0.0.1:5433). Cleanup disables the
P1 immutability trigger with session_replication_role = replica (superuser).
"""
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest
from libs.perception.evidence import Evidence, EvidenceStore, build_evidence
from libs.perception.observation import EvidenceCreate, QualityClass

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3)",
            tenant_id,
            f"ev-{tenant_id}",
            f"evslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    """Delete the test tenant and its evidence (bypassing the P1 trigger)."""
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute("DELETE FROM evidence WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM observations WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
        await conn.execute("SET session_replication_role = origin")
    finally:
        await conn.close()


def make_evidence(tenant_id: uuid.UUID, observation_ids: list[uuid.UUID]) -> Evidence:
    return build_evidence(
        EvidenceCreate(
            tenant_id=tenant_id,
            observation_ids=observation_ids,
            organization_type="resource_exhaustion_evidence",
            description=(
                "Within 5.0 min on source 00000000-0000-0000-0000-000000000002: "
                "cpu_utilization_percent=94.2, memory_usage_percent=88.0, "
                "disk_usage_percent=91.0."
            ),
            quality_class=QualityClass.Q1,
            weight=0.88,
        )
    )


@pytest.fixture
async def evidence_store():
    instance = EvidenceStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


async def test_save_evidence_and_read_back(evidence_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        observation_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        evidence = make_evidence(tenant_id, observation_ids)
        row = await evidence_store.save_evidence(evidence)
        assert row["id"] == evidence.id
        assert row["quality_class"] == "Q1"
        assert float(row["weight"]) == pytest.approx(0.88)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT observation_ids, quality_class, weight, description "
                "FROM evidence WHERE id = $1",
                evidence.id,
            )
        finally:
            await conn.close()
        assert selected["observation_ids"] == observation_ids
        assert selected["quality_class"] == "Q1"
        assert float(selected["weight"]) == pytest.approx(0.88)
        assert "cpu_utilization_percent=94.2" in selected["description"]
    finally:
        await _cleanup_tenant(tenant_id)


async def test_evidence_immutability_trigger_blocks_update_and_delete(evidence_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        evidence = make_evidence(tenant_id, [uuid.uuid4()])
        await evidence_store.save_evidence(evidence)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE evidence SET description = 'mutated' WHERE id = $1",
                    evidence.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute("DELETE FROM evidence WHERE id = $1", evidence.id)
        finally:
            await conn.close()
    finally:
        await _cleanup_tenant(tenant_id)


async def test_evidence_save_is_idempotent(evidence_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        evidence = make_evidence(tenant_id, [uuid.uuid4()])
        first = await evidence_store.save_evidence(evidence)
        assert first is not None
        second = await evidence_store.save_evidence(evidence)
        assert second is None
        assert await evidence_store.evidence_exists(id=evidence.id) is True

        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM evidence WHERE id = $1", evidence.id
            )
        finally:
            await conn.close()
        assert count == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_build_evidence_assigns_created_at_now(evidence_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        before = datetime.now(UTC)
        evidence = make_evidence(tenant_id, [uuid.uuid4()])
        await evidence_store.save_evidence(evidence)
        after = datetime.now(UTC)
        conn = await asyncpg.connect(DSN_RAW)
        try:
            organized_at = await conn.fetchval(
                "SELECT organized_at FROM evidence WHERE id = $1", evidence.id
            )
        finally:
            await conn.close()
        assert before <= organized_at <= after
        print("DEBUG py", evidence.organized_at, "before", before, "after", after, "db", organized_at)
    finally:
        await _cleanup_tenant(tenant_id)