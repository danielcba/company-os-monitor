"""H1 fix — Cross-tenant update isolation for Decision outcomes.

Verifies that the gateway's submit_outcomes enforces tenant_id at the SQL
write level, not just the preceding SELECT. Two tenants cannot interfere
with each other's decision lifecycle even if they know the UUID.
"""
from __future__ import annotations

import inspect
import json
import os
import socket
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[2]
DSN = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
)
PG_DSN = DSN.replace("postgresql+asyncpg://", "postgresql://")

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "gateway" / "api-gateway"))

from src.decisions import DecisionNotFoundError, DecisionReadStore  # noqa: E402

EXPECTED_OUTCOMES_COUNT = 2


def _db_available() -> bool:
    """Check if PostgreSQL is reachable."""
    try:
        sock = socket.create_connection(("127.0.0.1", 5433), timeout=2)
        sock.close()
    except (ConnectionRefusedError, OSError):
        return False
    else:
        return True


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL not available on localhost:5433",
)


async def _ensure_tenant(conn, tenant_id: uuid.UUID) -> None:
    await conn.execute(
        "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
        "ON CONFLICT (id) DO NOTHING",
        tenant_id,
        f"h1-{tenant_id.hex[:8]}",
        f"h1-{tenant_id.hex}",
    )


async def _create_decision(conn, tenant_id: uuid.UUID) -> uuid.UUID:
    decision_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO decisions (id, tenant_id, recommendation_id, confidence_id,
                               authority_id, commitment, expected_outcomes,
                               risk_tolerance, status, committed_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10)
        """,
        decision_id,
        tenant_id,
        uuid.uuid4(),  # recommendation_id
        uuid.uuid4(),  # confidence_id
        uuid.uuid4(),  # authority_id
        "test commitment",
        json.dumps([{"prediction": "p1", "verifiable_by": "v1", "deadline": "2026-09-01"}]),
        "low",
        "committed",
        datetime.now(UTC),
    )
    return decision_id


@pytest.fixture
def decision_store():
    return DecisionReadStore(dsn=DSN)


@pytest.mark.asyncio
async def test_tenant_a_updates_own_decision(decision_store):
    """Tenant A successfully updates outcomes on their own decision."""
    tenant_a = uuid.uuid4()
    conn = await asyncpg.connect(PG_DSN)
    try:
        await _ensure_tenant(conn, tenant_a)
        decision_id = await _create_decision(conn, tenant_a)
    finally:
        await conn.close()

    result = await decision_store.submit_outcomes(
        tenant_id=tenant_a,
        decision_id=decision_id,
        actual_outcomes=[{"prediction": "p1", "observed": True}],
        executed_at=datetime.now(UTC),
    )
    assert result["status"] == "outcomes_submitted"
    assert result["decision"]["actual_outcomes"] is not None
    assert result["decision"]["id"] == str(decision_id)


@pytest.mark.asyncio
async def test_tenant_a_cannot_update_tenant_b_decision(decision_store):
    """Tenant A's update on Tenant B's decision must not modify it."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    conn = await asyncpg.connect(PG_DSN)
    try:
        await _ensure_tenant(conn, tenant_a)
        await _ensure_tenant(conn, tenant_b)
        decision_id_b = await _create_decision(conn, tenant_b)
    finally:
        await conn.close()

    # Tenant A tries to update Tenant B's decision — should raise 404.
    with pytest.raises(DecisionNotFoundError):
        await decision_store.submit_outcomes(
            tenant_id=tenant_a,
            decision_id=decision_id_b,
            actual_outcomes=[{"prediction": "p1", "observed": True}],
        )

    # Verify the decision was NOT modified (actual_outcomes remains NULL).
    conn = await asyncpg.connect(PG_DSN)
    try:
        row = await conn.fetchrow(
            "SELECT actual_outcomes FROM decisions WHERE id = $1",
            decision_id_b,
        )
        assert row["actual_outcomes"] is None, (
            "Cross-tenant update leaked through — actual_outcomes should be NULL"
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_nonexistent_decision_raises_404(decision_store):
    """Updating a non-existent decision raises DecisionNotFoundError."""
    tenant_a = uuid.uuid4()
    conn = await asyncpg.connect(PG_DSN)
    try:
        await _ensure_tenant(conn, tenant_a)
    finally:
        await conn.close()

    with pytest.raises(DecisionNotFoundError):
        await decision_store.submit_outcomes(
            tenant_id=tenant_a,
            decision_id=uuid.uuid4(),
            actual_outcomes=[{"prediction": "p1", "observed": True}],
        )


@pytest.mark.asyncio
async def test_update_sql_contains_tenant_scope():
    """The UPDATE SQL in submit_outcomes must include tenant_id in WHERE."""
    source = inspect.getsource(DecisionReadStore.submit_outcomes)
    assert "AND tenant_id = :tenant_id" in source, (
        "UPDATE SQL must include tenant_id in WHERE clause for defense-in-depth"
    )


@pytest.mark.asyncio
async def test_cross_tenant_update_does_not_corrupt_data(decision_store):
    """Even if Tenant A knows Tenant B's decision UUID, no data is corrupted."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    conn = await asyncpg.connect(PG_DSN)
    try:
        await _ensure_tenant(conn, tenant_a)
        await _ensure_tenant(conn, tenant_b)
        decision_id_b = await _create_decision(conn, tenant_b)
    finally:
        await conn.close()

    # Read original state.
    conn = await asyncpg.connect(PG_DSN)
    try:
        original = await conn.fetchrow(
            "SELECT status, commitment FROM decisions WHERE id = $1",
            decision_id_b,
        )
    finally:
        await conn.close()

    # Tenant A attempts cross-tenant update.
    with pytest.raises(DecisionNotFoundError):
        await decision_store.submit_outcomes(
            tenant_id=tenant_a,
            decision_id=decision_id_b,
            actual_outcomes=[{"prediction": "p1", "observed": True}],
        )

    # Verify original state unchanged.
    conn = await asyncpg.connect(PG_DSN)
    try:
        after = await conn.fetchrow(
            "SELECT status, commitment FROM decisions WHERE id = $1",
            decision_id_b,
        )
        assert after["status"] == original["status"]
        assert after["commitment"] == original["commitment"]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_learning_loop_remains_intact(decision_store):
    """Learning loop integration is unaffected by the tenant_id fix."""
    tenant_a = uuid.uuid4()
    conn = await asyncpg.connect(PG_DSN)
    try:
        await _ensure_tenant(conn, tenant_a)
        decision_id = await _create_decision(conn, tenant_a)
    finally:
        await conn.close()

    result = await decision_store.submit_outcomes(
        tenant_id=tenant_a,
        decision_id=decision_id,
        actual_outcomes=[
            {"prediction": "p1", "observed": True},
            {"prediction": "p2", "observed": False},
        ],
        executed_at=datetime.now(UTC),
    )
    assert result["status"] == "outcomes_submitted"
    assert len(result["decision"]["actual_outcomes"]) == EXPECTED_OUTCOMES_COUNT
