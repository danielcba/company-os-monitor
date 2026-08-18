"""Integration tests for ObservationStore against the running Postgres database.

Requires the sandbox infra (postgres at 127.0.0.1:5433). Uses a throwaway tenant
whose cascade delete removes every observation bearing its tenant_id.
"""
import json
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest
from libs.cognitive_core.observation_bus import Observation
from libs.perception.store import ObservationStore

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3)",
            tenant_id,
            f"test-{tenant_id}",
            f"slug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    """Delete the test tenant and its observations (bypassing the P1 trigger).

    The P1 immutability trigger blocks deletes on the observations hypertable,
    so the cleanup transaction runs with triggers disabled (superuser required).
    The FK cascade alone would not remove rows because the trigger raises first.
    """
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute("DELETE FROM observations WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
        await conn.execute("SET session_replication_role = origin")
    finally:
        await conn.close()


@pytest.fixture
async def store():
    instance = ObservationStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


async def test_save_observation_and_read_back(store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        obs_id = uuid.uuid4()
        captured_at = datetime.now(UTC)
        observation = Observation(
            id=obs_id,
            tenant_id=tenant_id,
            source_id=uuid.uuid4(),
            source_type="linux_agent",
            fact_type="cpu_utilization_percent",
            fact_value={"value": 87.5},
            unit="percent",
            captured_at=captured_at,
            quality_class="Q1",
            raw_payload={"cpu_times": {"user": 1}},
        )
        row = await store.save_observation(observation)
        assert row["id"] == obs_id
        assert row["fact_type"] == "cpu_utilization_percent"
        assert row["quality_class"] == "Q1"

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT fact_value, quality_class FROM observations "
                "WHERE id = $1 AND captured_at = $2",
                obs_id,
                captured_at,
            )
        finally:
            await conn.close()
        assert json.loads(selected["fact_value"]) == {"value": 87.5}
        assert selected["quality_class"] == "Q1"
    finally:
        await _cleanup_tenant(tenant_id)


async def test_immutability_trigger_blocks_update(store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        obs_id = uuid.uuid4()
        captured_at = datetime.now(UTC)
        observation = Observation(
            id=obs_id,
            tenant_id=tenant_id,
            source_id=uuid.uuid4(),
            source_type="linux_agent",
            fact_type="memory_usage",
            fact_value={"free_bytes": 1000, "total_bytes": 2000},
            unit="bytes",
            captured_at=captured_at,
            quality_class="Q1",
            raw_payload={},
        )
        await store.save_observation(observation)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE observations SET fact_value = '{}' "
                    "WHERE id = $1 AND captured_at = $2",
                    obs_id,
                    captured_at,
                )
        finally:
            await conn.close()
    finally:
        await _cleanup_tenant(tenant_id)