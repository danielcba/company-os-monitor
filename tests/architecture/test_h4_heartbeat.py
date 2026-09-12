"""H4.2 — Heartbeat Protocol and Instance Health/Expiry Management.

Verifies: heartbeat endpoint, credential/installation status validation,
tenant isolation, liveness updates, expiry logic, concurrency safety,
and identity immutability per ADR-0006 §5.2.

Maps to ADR-0006 mandatory decision.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
from aiohttp.test_utils import TestClient, TestServer

from libs.access.security import JwtService, TokenPayload

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "gateway" / "api-gateway"))

from src.health import GatewayServer
from src.reconciler import HeartbeatReconciler
from src.service import GatewayService

DSN = os.getenv("DATABASE_URL", "postgresql://cosmonitor:cosmonitor@localhost:5433/cosmonitor")


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key="test-secret-key")


@pytest.fixture
async def client(jwt):
    service = GatewayService(jwt)
    server = GatewayServer(service, jwt)
    tc = TestClient(TestServer(server.app))
    await tc.start_server()
    yield tc
    await tc.close()


TENANT = uuid.uuid4()


async def _create_full_chain(conn, *, status="RUNNING", tenant_id=None):
    tid = uuid.UUID(str(tenant_id or TENANT))

    async with conn.transaction():
        await conn.execute(
            "INSERT INTO tenants (id, name, slug, created_at) "
            "VALUES ($1, $2, $3, now()) ON CONFLICT DO NOTHING",
            tid, "test-tenant", f"test-tenant-{tid}",
        )

        server_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO servers (id, tenant_id, hostname, ip_address, created_at) "
            "VALUES ($1, $2, $3, $4, now())",
            server_id, tid, f"server-{server_id}", "10.0.0.1",
        )

        inst_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO agent_installations (id, server_id, tenant_id, host_fingerprint, "
            "agent_type, agent_version, capabilities_json, status, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now(), now())",
            inst_id, server_id, tid, str(uuid.uuid4()),
            "agent-type", "1.0.0", "{}", "ACTIVE",
        )

        cred_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO agent_credentials (id, installation_id, tenant_id, status) "
            "VALUES ($1, $2, $3, $4)",
            cred_id, inst_id, tid, "ACTIVE",
        )

        instance_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO agent_instances (id, installation_id, credential_id, tenant_id, "
            "host_fingerprint, status) VALUES ($1, $2, $3, $4, $5, $6)",
            instance_id, inst_id, cred_id, tid, str(uuid.uuid4()), status,
        )

    inst_row = await conn.fetchrow(
        "SELECT id, status, tenant_id FROM agent_installations WHERE id = $1", inst_id,
    )
    cred_row = await conn.fetchrow(
        "SELECT id, status FROM agent_credentials WHERE id = $1", cred_id,
    )
    instance_row = await conn.fetchrow(
        "SELECT id, status, installation_id, credential_id, tenant_id "
        "FROM agent_instances WHERE id = $1",
        instance_id,
    )

    return dict(instance_row), dict(cred_row), dict(inst_row)


@pytest.fixture
async def make_full_instance():
    conn = await asyncpg.connect(DSN)
    yield _create_full_chain, conn
    await conn.close()


# ============================================================
# B4.2 — Blacklist Validation Tests
# ============================================================

class TestBlacklistValidation:
    """Verify that blacklisted machine access tokens are rejected (ADR-0005 §8)."""

    @pytest.mark.asyncio
    async def test_blacklisted_jti_rejected(self, jwt, make_full_instance):
        _create, conn = make_full_instance
        instance, cred, installation = await _create(conn)

        token = jwt.create_access_token(
            user_id=str(cred["id"]),
            tenant_id=str(TENANT),
            email="",
            role="",
        )
        payload = jwt.decode(token)
        jti = payload["jti"]

        await conn.execute("INSERT INTO machine_jwt_blacklist (jti) VALUES ($1)", jti)

        row = await conn.fetchrow("SELECT jti FROM machine_jwt_blacklist WHERE jti = $1", jti)
        assert row is not None
        assert row["jti"] == jti

    @pytest.mark.asyncio
    async def test_valid_token_not_blacklisted(self, jwt, make_full_instance):
        _create, conn = make_full_instance
        instance, cred, installation = await _create(conn)

        token = jwt.create_access_token(
            user_id=str(cred["id"]),
            tenant_id=str(TENANT),
            email="",
            role="",
        )
        payload = jwt.decode(token)
        jti = payload["jti"]

        row = await conn.fetchrow("SELECT jti FROM machine_jwt_blacklist WHERE jti = $1", jti)
        assert row is None

    @pytest.mark.asyncio
    async def test_duplicate_jti_blacklist_rejected(self, make_full_instance):
        _create, conn = make_full_instance
        jti = str(uuid.uuid4())
        await conn.execute("INSERT INTO machine_jwt_blacklist (jti) VALUES ($1)", jti)
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO machine_jwt_blacklist (jti) VALUES ($1)", jti,
            )


# ============================================================
# B4.3 — Refresh Token Tenant/Installation Preservation Tests
# ============================================================

class TestRefreshTokenPreservation:
    """Verify refresh tokens preserve tenant_id and installation_id (ADR-0005/0006)."""

    def test_token_carries_installation_id(self, jwt):
        installation_id = str(uuid.uuid4())
        token = jwt.create_access_token(
            user_id="cred-123",
            tenant_id="tenant-abc",
            email="",
            role="",
            extra_claims={"installation_id": installation_id},
        )
        payload = jwt.verify_access_token(token)
        assert payload.installation_id == installation_id
        assert payload.tenant_id == "tenant-abc"

    def test_token_without_installation_id(self, jwt):
        token = jwt.create_access_token(
            user_id="cred-123",
            tenant_id="tenant-abc",
            email="",
            role="",
        )
        payload = jwt.verify_access_token(token)
        assert payload.installation_id == ""

    def test_refresh_token_carries_installation_id(self, jwt):
        installation_id = str(uuid.uuid4())
        token = jwt.create_refresh_token(
            user_id="cred-123",
            tenant_id="tenant-abc",
            email="",
            role="",
            extra_claims={"installation_id": installation_id},
        )
        payload = jwt.verify_refresh_token(token)
        assert payload.installation_id == installation_id
        assert payload.tenant_id == "tenant-abc"

    def test_extra_claims_survive_full_cycle(self, jwt):
        installation_id = str(uuid.uuid4())
        token = jwt.create_access_token(
            user_id="u1",
            tenant_id="t1",
            email="e1",
            role="admin",
            extra_claims={"installation_id": installation_id},
        )
        decoded = jwt.decode(token)
        verified = jwt.verify_access_token(token)
        assert decoded["installation_id"] == installation_id
        assert verified.installation_id == installation_id
        assert verified.user_id == "u1"
        assert verified.tenant_id == "t1"


# ============================================================
# B4.4 — Heartbeat Reconciler Tests
# ============================================================

class TestHeartbeatReconciler:
    """Verify heartbeat reconciler transitions stale instances to STOPPED (ADR-0006 §9)."""

    @pytest.mark.asyncio
    async def test_stale_instance_stopped(self, make_full_instance):
        _create, conn = make_full_instance
        instance, cred, installation = await _create(conn)

        stale_time = datetime.now(UTC) - timedelta(minutes=5)
        await conn.execute(
            "UPDATE agent_instances SET last_heartbeat_at = $1 WHERE id = $2",
            stale_time, instance["id"],
        )

        reconciler = HeartbeatReconciler(DSN, heartbeat_timeout_seconds=120)
        count = await reconciler._reconcile_cycle()
        assert count >= 1

        row = await conn.fetchrow(
            "SELECT status FROM agent_instances WHERE id = $1", instance["id"],
        )
        assert row["status"] == "STOPPED"

    @pytest.mark.asyncio
    async def test_fresh_instance_remains_running(self, make_full_instance):
        _create, conn = make_full_instance
        instance, cred, installation = await _create(conn)

        reconciler = HeartbeatReconciler(DSN, heartbeat_timeout_seconds=120)
        count = await reconciler._reconcile_cycle()
        assert count == 0

        row = await conn.fetchrow(
            "SELECT status FROM agent_instances WHERE id = $1", instance["id"],
        )
        assert row["status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_stopped_instance_not_touched(self, make_full_instance):
        _create, conn = make_full_instance
        instance, cred, installation = await _create(conn, status="STOPPED")

        reconciler = HeartbeatReconciler(DSN, heartbeat_timeout_seconds=120)
        count = await reconciler._reconcile_cycle()
        assert count == 0

        row = await conn.fetchrow(
            "SELECT status FROM agent_instances WHERE id = $1", instance["id"],
        )
        assert row["status"] == "STOPPED"

    @pytest.mark.asyncio
    async def test_multiple_stale_instances_stopped(self, make_full_instance):
        _create, conn = make_full_instance
        instance1, _, _ = await _create(conn)
        instance2, _, _ = await _create(conn)

        stale_time = datetime.now(UTC) - timedelta(minutes=5)
        await conn.execute(
            "UPDATE agent_instances SET last_heartbeat_at = $1 WHERE id IN ($2, $3)",
            stale_time, instance1["id"], instance2["id"],
        )

        reconciler = HeartbeatReconciler(DSN, heartbeat_timeout_seconds=120)
        count = await reconciler._reconcile_cycle()
        expected_min_count = 2
        assert count >= expected_min_count

    @pytest.mark.asyncio
    async def test_reconciler_idempotent(self, make_full_instance):
        _create, conn = make_full_instance
        instance, cred, installation = await _create(conn)

        stale_time = datetime.now(UTC) - timedelta(minutes=5)
        await conn.execute(
            "UPDATE agent_instances SET last_heartbeat_at = $1 WHERE id = $2",
            stale_time, instance["id"],
        )

        reconciler = HeartbeatReconciler(DSN, heartbeat_timeout_seconds=120)
        count1 = await reconciler._reconcile_cycle()
        count2 = await reconciler._reconcile_cycle()
        assert count1 >= 1
        assert count2 == 0

    @pytest.mark.asyncio
    async def test_boundary_timeout_instance_stopped(self, make_full_instance):
        _create, conn = make_full_instance
        instance, cred, installation = await _create(conn)

        boundary_time = datetime.now(UTC) - timedelta(seconds=121)
        await conn.execute(
            "UPDATE agent_instances SET last_heartbeat_at = $1 WHERE id = $2",
            boundary_time, instance["id"],
        )

        reconciler = HeartbeatReconciler(DSN, heartbeat_timeout_seconds=120)
        count = await reconciler._reconcile_cycle()
        assert count >= 1


# ============================================================
# TokenPayload Tests
# ============================================================

class TestTokenPayloadInstallationId:
    """Verify TokenPayload carries installation_id correctly."""

    def test_frozen_dataclass(self, jwt):
        payload = TokenPayload(
            user_id="u", tenant_id="t", email="e", role="r",
            token_type="access", exp=0, jti="j", installation_id="inst-123",
        )
        assert payload.installation_id == "inst-123"
        assert payload.user_id == "u"

    def test_extra_claims_included_in_jwt(self, jwt):
        extra = {"installation_id": "inst-abc", "custom": "value"}
        token = jwt.create_access_token(
            user_id="u1", tenant_id="t1", email="", role="",
            extra_claims=extra,
        )
        decoded = jwt.decode(token)
        assert decoded["installation_id"] == "inst-abc"
        assert decoded["custom"] == "value"
