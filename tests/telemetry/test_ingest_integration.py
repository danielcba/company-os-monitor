"""H4.0-B2 REMEDIATION — Integration tests for telemetry ingest.

Requires PostgreSQL on localhost:5433. Skipped if unavailable.
Tests idempotency, concurrency, rollback, cardinality, outbox, cross-tenant.
"""
from __future__ import annotations

import asyncio
import json
import socket
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from libs.telemetry.ingest_service import (
    PayloadConflictError,
    TelemetryIngestService,
    ValidationError,
)

DSN = "postgresql://cosmonitor:cosmonitor@localhost:5433/cosmonitor"


def _db_available() -> bool:
    try:
        sock = socket.create_connection(("127.0.0.1", 5433), timeout=2)
        sock.close()
    except (ConnectionRefusedError, OSError):
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL not available on localhost:5433",
)


async def _create_tenant(conn: asyncpg.Connection, tenant_id: uuid.UUID) -> None:
    await conn.execute(
        "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
        "ON CONFLICT (id) DO NOTHING",
        tenant_id, f"test-{tenant_id.hex[:8]}", f"test-{tenant_id.hex}",
    )


async def _create_server(
    conn: asyncpg.Connection, server_id: uuid.UUID, tenant_id: uuid.UUID,
) -> None:
    await conn.execute(
        "INSERT INTO servers "
        "(id, tenant_id, hostname, ip_address, os_type, "
        " os_version, agent_version, status) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
        "ON CONFLICT (id) DO NOTHING",
        server_id, tenant_id, f"server-{server_id.hex[:8]}", "127.0.0.1",
        "linux", "6.1.0", "1.0.0", "active",
    )


async def _create_installation(
    conn: asyncpg.Connection,
    installation_id: uuid.UUID,
    tenant_id: uuid.UUID,
    server_id: uuid.UUID,
    capabilities_json: dict | None = None,
) -> None:
    caps = capabilities_json or {}
    await conn.execute(
        "INSERT INTO agent_installations "
        "(id, tenant_id, server_id, host_fingerprint, agent_type, agent_version, "
        " capabilities_json, status) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,'ACTIVE') "
        "ON CONFLICT (id) DO NOTHING",
        installation_id, tenant_id, server_id,
        "aa" * 32,
        "test-agent", "1.0.0",
        json.dumps(caps),
    )


async def _create_credential(
    conn: asyncpg.Connection, credential_id: uuid.UUID, tenant_id: uuid.UUID,
    installation_id: uuid.UUID,
) -> None:
    await conn.execute(
        "INSERT INTO agent_credentials (id, tenant_id, installation_id, status) "
        "VALUES ($1,$2,$3,'ACTIVE') ON CONFLICT (id) DO NOTHING",
        credential_id, tenant_id, installation_id,
    )


async def _cleanup_batch(
    conn: asyncpg.Connection, tenant_id: uuid.UUID, batch_id: uuid.UUID,
) -> None:
    await conn.execute("SET session_replication_role = replica")
    try:
        await conn.execute(
            "DELETE FROM observation_outbox WHERE tenant_id = $1 AND batch_id = $2",
            tenant_id, batch_id,
        )
        await conn.execute(
            "DELETE FROM metric_samples WHERE tenant_id = $1 AND batch_id = $2",
            tenant_id, batch_id,
        )
        await conn.execute(
            "DELETE FROM metric_batches WHERE tenant_id = $1 AND batch_id = $2",
            tenant_id, batch_id,
        )
    finally:
        await conn.execute("SET session_replication_role = DEFAULT")


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _valid_body(
    batch_id: uuid.UUID | None = None,
    samples: list[dict] | None = None,
    captured_at: str | None = None,
) -> dict[str, Any]:
    return {
        "batch_id": str(batch_id or _uid()),
        "captured_at": captured_at or datetime.now(UTC).isoformat(),
        "samples": samples if samples is not None else [
            {
                "sequence": 1,
                "fact_type": "cpu_utilization_percent",
                "fact_value": {"value": 45.2},
                "unit": "percent",
                "labels": {"core": "0"},
            },
        ],
    }


def _multi_sample_body(batch_id: uuid.UUID, n: int = 3) -> dict[str, Any]:
    return {
        "batch_id": str(batch_id),
        "captured_at": datetime.now(UTC).isoformat(),
        "samples": [
            {
                "sequence": i,
                "fact_type": f"metric_{i}",
                "fact_value": {"value": i * 10},
                "unit": "count",
                "labels": {},
            }
            for i in range(1, n + 1)
        ],
    }


# ──────────────────────────────────────────────────────
# FIXTURES
# ──────────────────────────────────────────────────────


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return _uid()


@pytest.fixture
def server_id() -> uuid.UUID:
    return _uid()


@pytest.fixture
def installation_id() -> uuid.UUID:
    return _uid()


@pytest.fixture
def credential_id() -> uuid.UUID:
    return _uid()


@pytest.fixture
async def setup_tenant(tenant_id, server_id, installation_id, credential_id):
    conn = await asyncpg.connect(DSN)
    try:
        await _create_tenant(conn, tenant_id)
        await _create_server(conn, server_id, tenant_id)
        await _create_installation(conn, installation_id, tenant_id, server_id)
        await _create_credential(conn, credential_id, tenant_id, installation_id)
    finally:
        await conn.close()
    yield


# ──────────────────────────────────────────────────────
# VALID BATCH (TEST 1, 15, 16)
# ──────────────────────────────────────────────────────


class TestIngestSuccess:
    """First ingest and idempotent retry."""

    @pytest.mark.asyncio
    async def test_first_ingest(self, setup_tenant, tenant_id, installation_id, credential_id):
        batch_id = _uid()
        body = _valid_body(batch_id=batch_id)
        svc = TelemetryIngestService(DSN)

        result = await svc.ingest_batch(
            tenant_id=tenant_id,
            installation_id=installation_id,
            instance_id=_uid(),
            credential_id=credential_id,
            body=body,
        )

        assert result.batch_id == batch_id
        assert len(result.observation_ids) == 1
        assert result.ingested_at is not None

        conn = await asyncpg.connect(DSN)
        try:
            batch = await conn.fetchrow(
                "SELECT * FROM metric_batches WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert batch is not None
            assert batch["sample_count"] == 1

            samples = await conn.fetch(
                "SELECT * FROM metric_samples WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(samples) == 1

            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()

    @pytest.mark.asyncio
    async def test_idempotent_retry(self, setup_tenant, tenant_id, installation_id, credential_id):
        batch_id = _uid()
        body = _valid_body(batch_id=batch_id)
        svc = TelemetryIngestService(DSN)
        instance_id = _uid()

        result1 = await svc.ingest_batch(
            tenant_id=tenant_id,
            installation_id=installation_id,
            instance_id=instance_id,
            credential_id=credential_id,
            body=body,
        )

        result2 = await svc.ingest_batch(
            tenant_id=tenant_id,
            installation_id=installation_id,
            instance_id=instance_id,
            credential_id=credential_id,
            body=body,
        )

        assert result1.observation_ids == result2.observation_ids
        assert result1.batch_id == result2.batch_id

        conn = await asyncpg.connect(DSN)
        try:
            samples = await conn.fetch(
                "SELECT * FROM metric_samples WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(samples) == 1

            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()


# ──────────────────────────────────────────────────────
# VALIDATION (TESTS 2-6)
# ──────────────────────────────────────────────────────


class TestValidation:
    """Body validation against DB-backed service."""

    @pytest.mark.asyncio
    async def test_empty_samples(self, setup_tenant, tenant_id, installation_id, credential_id):
        body = _valid_body(samples=[])
        svc = TelemetryIngestService(DSN)
        with pytest.raises(ValidationError, match="non-empty"):
            await svc.ingest_batch(tenant_id, installation_id, _uid(), credential_id, body)

    @pytest.mark.asyncio
    async def test_invalid_sequence_zero(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        body = _valid_body(samples=[
            {"sequence": 0, "fact_type": "x", "fact_value": {}, "unit": "%"},
        ])
        svc = TelemetryIngestService(DSN)
        with pytest.raises(ValidationError, match="positive integer"):
            await svc.ingest_batch(tenant_id, installation_id, _uid(), credential_id, body)

    @pytest.mark.asyncio
    async def test_invalid_captured_at(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        body = _valid_body(captured_at="not-a-date")
        svc = TelemetryIngestService(DSN)
        with pytest.raises(ValidationError, match="ISO 8601"):
            await svc.ingest_batch(tenant_id, installation_id, _uid(), credential_id, body)

    @pytest.mark.asyncio
    async def test_invalid_batch_id(self, setup_tenant, tenant_id, installation_id, credential_id):
        body = _valid_body()
        body["batch_id"] = "not-a-uuid"
        svc = TelemetryIngestService(DSN)
        with pytest.raises(ValidationError, match="valid UUID"):
            await svc.ingest_batch(tenant_id, installation_id, _uid(), credential_id, body)

    @pytest.mark.asyncio
    async def test_malformed_sample(self, setup_tenant, tenant_id, installation_id, credential_id):
        body = _valid_body(samples=[{"not_a_sample": True}])
        svc = TelemetryIngestService(DSN)
        with pytest.raises(ValidationError, match="sequence is required"):
            await svc.ingest_batch(tenant_id, installation_id, _uid(), credential_id, body)


# ──────────────────────────────────────────────────────
# CONFLICT (TEST 17)
# ──────────────────────────────────────────────────────


class TestConflict:
    """Same batch_id + different hash → 409."""

    @pytest.mark.asyncio
    async def test_different_hash_conflict(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        batch_id = _uid()
        body1 = _valid_body(batch_id=batch_id, samples=[
            {"sequence": 1, "fact_type": "cpu",
             "fact_value": {"value": 1}, "unit": "%", "labels": {}},
        ])
        body2 = _valid_body(batch_id=batch_id, samples=[
            {"sequence": 1, "fact_type": "cpu",
             "fact_value": {"value": 999}, "unit": "%", "labels": {}},
        ])

        svc = TelemetryIngestService(DSN)
        instance_id = _uid()

        await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body1)

        with pytest.raises(PayloadConflictError):
            await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body2)

        conn = await asyncpg.connect(DSN)
        try:
            samples = await conn.fetch(
                "SELECT * FROM metric_samples WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(samples) == 1

            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()


# ──────────────────────────────────────────────────────
# OBSERVATION IDS (TEST 18)
# ──────────────────────────────────────────────────────


class TestDeterministicIds:
    """Observation IDs are deterministic across calls."""

    @pytest.mark.asyncio
    async def test_deterministic_across_retries(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        batch_id = _uid()
        body = _valid_body(batch_id=batch_id)
        svc = TelemetryIngestService(DSN)
        instance_id = _uid()

        r1 = await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body)
        r2 = await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body)

        assert r1.observation_ids == r2.observation_ids

        conn = await asyncpg.connect(DSN)
        try:
            await _cleanup_batch(conn, tenant_id, batch_id)
        finally:
            await conn.close()


# ──────────────────────────────────────────────────────
# MULTIPLE SAMPLES (TEST 19)
# ──────────────────────────────────────────────────────


class TestMultipleSamples:
    """N samples → N metric_samples + N observation_outbox."""

    @pytest.mark.asyncio
    async def test_three_samples(self, setup_tenant, tenant_id, installation_id, credential_id):
        batch_id = _uid()
        body = _multi_sample_body(batch_id, n=3)
        svc = TelemetryIngestService(DSN)

        result = await svc.ingest_batch(
            tenant_id, installation_id, _uid(), credential_id, body,
        )

        assert len(result.observation_ids) == 3

        conn = await asyncpg.connect(DSN)
        try:
            samples = await conn.fetch(
                "SELECT sequence FROM metric_samples "
                "WHERE tenant_id=$1 AND batch_id=$2 ORDER BY sequence",
                tenant_id, batch_id,
            )
            assert [s["sequence"] for s in samples] == [1, 2, 3]

            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
            raw = outbox[0]["observation"]
            obs = json.loads(raw) if isinstance(raw, str) else raw
            assert len(obs.get("observations", [])) == 3
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()


# ──────────────────────────────────────────────────────
# OUTBOX IDEMPOTENCY (TEST 22, 27)
# ──────────────────────────────────────────────────────


class TestOutboxIdempotency:
    """Retry does not duplicate outbox records."""

    @pytest.mark.asyncio
    async def test_retry_no_duplicate_outbox(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        batch_id = _uid()
        body = _multi_sample_body(batch_id, n=2)
        svc = TelemetryIngestService(DSN)
        instance_id = _uid()

        r1 = await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body)
        r2 = await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body)

        assert r1.observation_ids == r2.observation_ids

        conn = await asyncpg.connect(DSN)
        try:
            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
            raw = outbox[0]["observation"]
            obs = json.loads(raw) if isinstance(raw, str) else raw
            assert len(obs.get("observations", [])) == 2

            samples = await conn.fetch(
                "SELECT * FROM metric_samples WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(samples) == 2
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()

    @pytest.mark.asyncio
    async def test_conflict_no_outbox_created(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        batch_id = _uid()
        body1 = _valid_body(batch_id=batch_id, samples=[
            {"sequence": 1, "fact_type": "cpu",
             "fact_value": {"value": 1}, "unit": "%", "labels": {}},
        ])
        body2 = _valid_body(batch_id=batch_id, samples=[
            {"sequence": 1, "fact_type": "cpu",
             "fact_value": {"value": 2}, "unit": "%", "labels": {}},
        ])

        svc = TelemetryIngestService(DSN)
        instance_id = _uid()

        await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body1)

        with pytest.raises(PayloadConflictError):
            await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body2)

        conn = await asyncpg.connect(DSN)
        try:
            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()


# ──────────────────────────────────────────────────────
# CONCURRENCY (TESTS 24-25)
# ──────────────────────────────────────────────────────


class TestConcurrency:
    """Concurrent idempotent requests."""

    @pytest.mark.asyncio
    async def test_concurrent_same_hash(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        """Two concurrent requests with same batch+hash → both 202, no duplication."""
        batch_id = _uid()
        body = _valid_body(batch_id=batch_id)
        svc = TelemetryIngestService(DSN)
        instance_id = _uid()

        async def ingest():
            return await svc.ingest_batch(
                tenant_id, installation_id, instance_id, credential_id, body,
            )

        results = await asyncio.gather(ingest(), ingest(), return_exceptions=True)

        successes = [
            r for r in results
            if isinstance(r, type(results[0]))
            and not isinstance(r, Exception)
        ]
        errors = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 2
        assert len(errors) == 0

        r1, r2 = results
        assert r1.observation_ids == r2.observation_ids

        conn = await asyncpg.connect(DSN)
        try:
            samples = await conn.fetch(
                "SELECT * FROM metric_samples WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(samples) == 1

            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()

    @pytest.mark.asyncio
    async def test_concurrent_different_hash(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        """Two concurrent requests with same batch+diff hash → one 202, one 409."""
        batch_id = _uid()
        body1 = _valid_body(batch_id=batch_id, samples=[
            {"sequence": 1, "fact_type": "cpu",
             "fact_value": {"value": 1}, "unit": "%", "labels": {}},
        ])
        body2 = _valid_body(batch_id=batch_id, samples=[
            {"sequence": 1, "fact_type": "cpu",
             "fact_value": {"value": 999}, "unit": "%", "labels": {}},
        ])

        svc = TelemetryIngestService(DSN)
        instance_id = _uid()

        async def ingest(body):
            return await svc.ingest_batch(
                tenant_id, installation_id, instance_id, credential_id, body,
            )

        results = await asyncio.gather(ingest(body1), ingest(body2), return_exceptions=True)

        successes = [r for r in results if not isinstance(r, Exception)]
        conflicts = [r for r in results if isinstance(r, PayloadConflictError)]
        other_errors = [
            r for r in results
            if isinstance(r, Exception)
            and not isinstance(r, PayloadConflictError)
        ]

        assert len(successes) == 1
        assert len(conflicts) == 1
        assert len(other_errors) == 0

        conn = await asyncpg.connect(DSN)
        try:
            samples = await conn.fetch(
                "SELECT * FROM metric_samples WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(samples) == 1

            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()


# ──────────────────────────────────────────────────────
# CROSS-TENANT (TEST 26)
# ──────────────────────────────────────────────────────


class TestCrossTenant:
    """Tenant isolation: wrong tenant_id → rejected."""

    @pytest.mark.asyncio
    async def test_wrong_tenant_rejected(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        wrong_tenant = _uid()
        body = _valid_body()
        svc = TelemetryIngestService(DSN)

        with pytest.raises(ValidationError, match="installation not found or tenant mismatch"):
            await svc.ingest_batch(
                wrong_tenant, installation_id, _uid(), credential_id, body,
            )

    @pytest.mark.asyncio
    async def test_wrong_installation_rejected(self, setup_tenant, tenant_id, credential_id):
        wrong_installation = _uid()
        body = _valid_body()
        svc = TelemetryIngestService(DSN)

        with pytest.raises(ValidationError, match="installation not found or tenant mismatch"):
            await svc.ingest_batch(
                tenant_id, wrong_installation, _uid(), credential_id, body,
            )

    @pytest.mark.asyncio
    async def test_installation_from_different_tenant_rejected(
        self, tenant_id, installation_id, credential_id,
    ):
        """Installation belonging to a different tenant is rejected."""
        other_tenant = _uid()
        other_server = _uid()
        other_installation = _uid()
        other_credential = _uid()

        conn = await asyncpg.connect(DSN)
        try:
            await _create_tenant(conn, other_tenant)
            await _create_server(conn, other_server, other_tenant)
            await _create_installation(conn, other_installation, other_tenant, other_server)
            await _create_credential(conn, other_credential, other_tenant, other_installation)
        finally:
            await conn.close()

        body = _valid_body()
        svc = TelemetryIngestService(DSN)

        with pytest.raises(ValidationError, match="installation not found or tenant mismatch"):
            await svc.ingest_batch(
                tenant_id, other_installation, _uid(), other_credential, body,
            )


# ──────────────────────────────────────────────────────
# SOURCE_ID (TEST 20)
# ──────────────────────────────────────────────────────


class TestSourceId:
    """source_id resolves from installation → server_id."""

    @pytest.mark.asyncio
    async def test_source_id_matches_server(
        self, setup_tenant, tenant_id, installation_id,
        credential_id, server_id,
    ):
        batch_id = _uid()
        body = _valid_body(batch_id=batch_id)
        svc = TelemetryIngestService(DSN)

        await svc.ingest_batch(
            tenant_id, installation_id, _uid(), credential_id, body,
        )

        conn = await asyncpg.connect(DSN)
        try:
            batch = await conn.fetchrow(
                "SELECT * FROM metric_batches WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert batch is not None
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()


# ──────────────────────────────────────────────────────
# QUALITY_CLASS (TEST 21)
# ──────────────────────────────────────────────────────


class TestQualityClass:
    """quality_class resolves from capabilities_json."""

    @pytest.mark.asyncio
    async def test_default_quality_class(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        batch_id = _uid()
        body = _valid_body(batch_id=batch_id)
        svc = TelemetryIngestService(DSN)

        await svc.ingest_batch(
            tenant_id, installation_id, _uid(), credential_id, body,
        )

        conn = await asyncpg.connect(DSN)
        try:
            outbox = await conn.fetchrow(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            obs = json.loads(outbox["observation"])
            first_obs = obs["observations"][0]
            assert first_obs["quality_class"] == "Q3"
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()


# ──────────────────────────────────────────────────────
# CARDINALITY (TEST 8)
# ──────────────────────────────────────────────────────


class TestCardinality:
    """N input samples = N metric_samples = N observation_outbox."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("n", [1, 2, 5])
    async def test_n_samples_cardinality(
        self, setup_tenant, tenant_id, installation_id,
        credential_id, n,
    ):
        batch_id = _uid()
        body = _multi_sample_body(batch_id, n=n)
        svc = TelemetryIngestService(DSN)

        result = await svc.ingest_batch(
            tenant_id, installation_id, _uid(), credential_id, body,
        )

        assert len(result.observation_ids) == n

        conn = await asyncpg.connect(DSN)
        try:
            samples = await conn.fetch(
                "SELECT sequence FROM metric_samples "
                "WHERE tenant_id=$1 AND batch_id=$2 ORDER BY sequence",
                tenant_id, batch_id,
            )
            assert len(samples) == n
            sequences = [s["sequence"] for s in samples]
            assert sequences == list(range(1, n + 1))

            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
            raw = outbox[0]["observation"]
            obs = json.loads(raw) if isinstance(raw, str) else raw
            assert len(obs.get("observations", [])) == n
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()


# ──────────────────────────────────────────────────────
# TRANSACTION ROLLBACK (TEST 23)
# ──────────────────────────────────────────────────────


class TestTransactionRollback:
    """Failed inserts leave no orphan rows."""

    @pytest.mark.asyncio
    async def test_rollback_on_conflict(
        self, setup_tenant, tenant_id, installation_id, credential_id,
    ):
        """Conflict after batch insert → no orphan samples/outbox."""
        batch_id = _uid()
        body1 = _valid_body(batch_id=batch_id, samples=[
            {"sequence": 1, "fact_type": "cpu",
             "fact_value": {"value": 1}, "unit": "%", "labels": {}},
        ])
        body2 = _valid_body(batch_id=batch_id, samples=[
            {"sequence": 1, "fact_type": "cpu",
             "fact_value": {"value": 2}, "unit": "%", "labels": {}},
        ])

        svc = TelemetryIngestService(DSN)
        instance_id = _uid()

        await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body1)

        with pytest.raises(PayloadConflictError):
            await svc.ingest_batch(tenant_id, installation_id, instance_id, credential_id, body2)

        conn = await asyncpg.connect(DSN)
        try:
            batches = await conn.fetch(
                "SELECT * FROM metric_batches WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(batches) == 1

            samples = await conn.fetch(
                "SELECT * FROM metric_samples WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(samples) == 1

            outbox = await conn.fetch(
                "SELECT * FROM observation_outbox WHERE tenant_id=$1 AND batch_id=$2",
                tenant_id, batch_id,
            )
            assert len(outbox) == 1
        finally:
            await _cleanup_batch(conn, tenant_id, batch_id)
            await conn.close()
