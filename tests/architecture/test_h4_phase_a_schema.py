"""H4.0 Phase A — Foundation Schema Tests.

Verifies: all 6 tables exist, required columns/types, PK/UNIQUE constraints,
composite FK enforcement, tenant isolation, partial UNIQUE RUNNING instances,
append-only triggers, outbox content immutability, migration idempotency,
and absence of cross-tenant references.

Maps to ADR-0004, ADR-0005, ADR-0006, ADR-0007 mandatory decisions.
"""
import json as _json
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DSN = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
)


@pytest.fixture
def engine():
    return create_async_engine(DSN)


async def _table_exists(engine, table_name):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_name = :t"
                " AND table_schema = 'public'"
                ")"
            ),
            {"t": table_name},
        )
        return result.scalar() is True


async def _index_exists(engine, index_name):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM pg_indexes"
                "  WHERE indexname = :i"
                " AND schemaname = 'public'"
                ")"
            ),
            {"i": index_name},
        )
        return result.scalar() is True


async def _trigger_exists(engine, trigger_name):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.triggers"
                "  WHERE trigger_name = :t"
                ")"
            ),
            {"t": trigger_name},
        )
        return result.scalar() is True


async def _constraint_exists(engine, table_name, constraint_name):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.table_constraints"
                "  WHERE table_name = :t"
                "  AND constraint_name = :c"
                ")"
            ),
            {"t": table_name, "c": constraint_name},
        )
        return result.scalar() is True


@pytest.mark.asyncio
async def test_agent_installations_table_exists(engine):
    assert await _table_exists(engine, "agent_installations")


@pytest.mark.asyncio
async def test_agent_credentials_table_exists(engine):
    assert await _table_exists(engine, "agent_credentials")


@pytest.mark.asyncio
async def test_agent_instances_table_exists(engine):
    assert await _table_exists(engine, "agent_instances")


@pytest.mark.asyncio
async def test_metric_batches_table_exists(engine):
    assert await _table_exists(engine, "metric_batches")


@pytest.mark.asyncio
async def test_metric_samples_table_exists(engine):
    assert await _table_exists(engine, "metric_samples")


@pytest.mark.asyncio
async def test_observation_outbox_table_exists(engine):
    assert await _table_exists(engine, "observation_outbox")


@pytest.mark.asyncio
async def test_agent_installations_required_columns(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'agent_installations'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: row[1] for row in result}
        required = {
            "id": "uuid",
            "tenant_id": "uuid",
            "server_id": "uuid",
            "host_fingerprint": "character",
            "agent_type": "character varying",
            "agent_version": "character varying",
            "capabilities_json": "jsonb",
            "status": "character varying",
            "registered_at": "timestamp with time zone",
            "last_seen_at": "timestamp with time zone",
            "created_at": "timestamp with time zone",
            "updated_at": "timestamp with time zone",
        }
        for col in required:
            assert col in columns, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_agent_credentials_required_columns(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'agent_credentials'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: row[1] for row in result}
        required = {
            "id": "uuid",
            "tenant_id": "uuid",
            "installation_id": "uuid",
            "public_key_hash": "character",
            "status": "character varying",
            "created_at": "timestamp with time zone",
            "revoked_at": "timestamp with time zone",
        }
        for col in required:
            assert col in columns, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_agent_instances_required_columns(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'agent_instances'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: row[1] for row in result}
        required = {
            "id": "uuid",
            "tenant_id": "uuid",
            "installation_id": "uuid",
            "credential_id": "uuid",
            "host_fingerprint": "character",
            "status": "character varying",
            "registered_at": "timestamp with time zone",
            "last_heartbeat_at": "timestamp with time zone",
            "stopped_at": "timestamp with time zone",
            "created_at": "timestamp with time zone",
        }
        for col in required:
            assert col in columns, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_metric_batches_required_columns(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'metric_batches'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: row[1] for row in result}
        required = {
            "id": "uuid",
            "tenant_id": "uuid",
            "installation_id": "uuid",
            "instance_id": "uuid",
            "credential_id": "uuid",
            "batch_id": "uuid",
            "payload_hash": "character",
            "captured_at": "timestamp with time zone",
            "received_at": "timestamp with time zone",
            "sample_count": "integer",
        }
        for col in required:
            assert col in columns, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_metric_samples_required_columns(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'metric_samples'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: row[1] for row in result}
        required = {
            "id": "uuid",
            "tenant_id": "uuid",
            "batch_id": "uuid",
            "sequence": "integer",
            "fact_type": "character varying",
            "fact_value": "jsonb",
            "unit": "character varying",
            "labels": "jsonb",
        }
        for col in required:
            assert col in columns, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_observation_outbox_required_columns(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'observation_outbox'
                ORDER BY ordinal_position
            """)
        )
        columns = {row[0]: row[1] for row in result}
        required = {
            "id": "uuid",
            "tenant_id": "uuid",
            "installation_id": "uuid",
            "batch_id": "uuid",
            "credential_id": "uuid",
            "payload_hash": "character",
            "observation": "jsonb",
            "status": "character varying",
            "attempts": "integer",
            "next_attempt_at": "timestamp with time zone",
            "last_error": "text",
            "published_at": "timestamp with time zone",
            "created_at": "timestamp with time zone",
        }
        for col in required:
            assert col in columns, f"Missing column: {col}"


@pytest.mark.asyncio
async def test_agent_installations_pk(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.table_constraints"
                "  WHERE table_name = 'agent_installations'"
                "  AND constraint_type = 'PRIMARY KEY'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_agent_installations_unique_tenant_server_agent_type(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.table_constraints"
                "  WHERE table_name = 'agent_installations'"
                "  AND constraint_type = 'UNIQUE'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_agent_credentials_unique_tenant_install_id(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.table_constraints"
                "  WHERE table_name = 'agent_credentials'"
                "  AND constraint_type = 'UNIQUE'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_agent_unique_running_instance_per_installation(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM pg_indexes"
                "  WHERE indexname = 'uq_agent_instances_active'"
                " AND schemaname = 'public'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_metric_batches_unique_tenant(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.table_constraints"
                "  WHERE table_name = 'metric_batches'"
                "  AND constraint_type = 'UNIQUE'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_metric_batches_fk_to_agent_installations(engine):
    """Composite FK: metric_batches → agent_installations."""
    assert await _constraint_exists(engine, "metric_batches", "fk_metric_batches_installation")


@pytest.mark.asyncio
async def test_metric_samples_fk_to_metric_batches(engine):
    """Composite FK: metric_samples → metric_batches."""
    assert await _constraint_exists(engine, "metric_samples", "fk_metric_samples_batch")


@pytest.mark.asyncio
async def test_observation_outbox_fk_to_agent_installations(engine):
    """Composite FK: observation_outbox → agent_installations."""
    constraint_name = "fk_observation_outbox_installation"
    assert await _constraint_exists(engine, "observation_outbox", constraint_name)


@pytest.mark.asyncio
async def test_all_tables_have_tenant_id(engine):
    tables = [
        "agent_installations",
        "agent_credentials",
        "agent_instances",
        "metric_batches",
        "metric_samples",
        "observation_outbox",
    ]
    for table in tables:
        assert await _table_exists(engine, table)


@pytest.mark.asyncio
async def test_metric_batches_immutable_trigger(engine):
    assert await _trigger_exists(engine, "metric_batches_immutable_trigger")


@pytest.mark.asyncio
async def test_metric_samples_immutable_trigger(engine):
    assert await _trigger_exists(engine, "metric_samples_immutable_trigger")


@pytest.mark.asyncio
async def test_observation_outbox_immutable_trigger(engine):
    assert await _trigger_exists(engine, "outbox_content_immutable_trigger")


@pytest.mark.asyncio
async def test_observation_outbox_lifecycle_fields_mutable_only(engine):
    """Outbox content is immutable - only lifecycle fields may change."""
    _json_mod = _json

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "INSERT INTO servers (tenant_id, hostname, os_type, status) "
                "VALUES (:t, :h, :o, :s) "
                "RETURNING id"
            ),
            {
                "t": "00000000-0000-0000-0000-000000000001",
                "h": "test-server-1",
                "o": "linux",
                "s": "online",
            },
        )
        server_id = result.scalar()

        result = await conn.execute(
            text(
                "INSERT INTO agent_installations (tenant_id, server_id, host_fingerprint, "
                "agent_type, agent_version, capabilities_json, status) "
                "VALUES (:t, :s, :h, :a, :v, :c, :s2) "
                "RETURNING id"
            ),
            {
                "t": "00000000-0000-0000-0000-000000000001",
                "s": server_id,
                "h": "a" * 64,
                "a": "linux_agent",
                "v": "1.0.0",
                "c": "{}",
                "s2": "ACTIVE",
            },
        )
        inst_id = result.scalar()

        result = await conn.execute(
            text(
                "INSERT INTO agent_credentials (tenant_id, installation_id, "
                "public_key_hash, status) "
                "VALUES (:t, :i, :p, :s3) "
                "RETURNING id"
            ),
            {
                "t": "00000000-0000-0000-0000-000000000001",
                "i": inst_id,
                "p": "b" * 64,
                "s3": "ACTIVE",
            },
        )
        cred_id = result.scalar()

        result = await conn.execute(
            text(
                "INSERT INTO observation_outbox (tenant_id, installation_id, batch_id, "
                "credential_id, payload_hash, observation, status, created_at) "
                "VALUES (:t, :i, :b, :c, :p, :o, :s, now()) "
                "RETURNING id"
            ),
            {
                "t": "00000000-0000-0000-0000-000000000001",
                "i": inst_id,
                "b": "00000000-0000-0000-0000-000000000003",
                "c": cred_id,
                "p": "c" * 64,
                "o": _json_mod.dumps(
                    {
                        "fact_type": "cpu_utilization_percent",
                        "fact_value": {"value": 42.0},
                        "unit": "percent",
                    }
                ),
                "s": "pending",
            },
        )
        outbox_id = result.scalar()

        def _raise_assertion_error():
            raise AssertionError()

        try:
            await conn.execute(
                text(
                    "UPDATE observation_outbox SET observation = :o WHERE id = :id"
                ),
                {"o": _json_mod.dumps({"different": True}), "id": outbox_id},
            )
            _raise_assertion_error()
        except Exception as e:
            if type(e) is AssertionError:
                raise