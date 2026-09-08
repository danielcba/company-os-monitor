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
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from libs.access.security import JwtService

# Local imports after sys.path modification
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "gateway" / "api-gateway"))

from src.health import GatewayServer
from src.service import GatewayService

DSN = (
    "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor"
    if not os.getenv("DATABASE_URL")
    else os.getenv("DATABASE_URL")
)


@pytest.fixture
def engine():
    """Create a new database engine for each test."""
    return create_async_engine(
        DSN or "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
        isolation_level="AUTOCOMMIT",
    )


@pytest.fixture
def jwt():
    """JwtService instance for creating auth tokens."""
    return JwtService(algorithm="HS256", secret_key="test-secret-key")


@pytest.fixture
async def client(jwt):
    """Test client for the gateway using TestServer."""
    service = GatewayService(jwt)
    server = GatewayServer(service, jwt)
    tc = TestClient(TestServer(server.app))
    await tc.start_server()
    yield tc
    await tc.close()


TENANT = uuid.uuid4()


def _params(**kwargs):
    """Return dict for SQLAlchemy text() :N parameter binding."""
    return kwargs


@pytest.fixture
async def make_full_instance(engine):
    """Fixture that creates the full chain: tenant → server → installation → credential → instance.

    All records are created in a single transaction so FK constraints are satisfied
    and IDs are consistent across all five tables (tenants, servers, agent_installations,
    agent_credentials, agent_instances).
    """

    async def _create(status="RUNNING"):
        tid = str(TENANT)

        async with engine.begin() as conn:
            # 1. Create tenant
            await conn.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, created_at) "
                    "VALUES (:1, :2, :3, now()) ON CONFLICT DO NOTHING"
                ),
                _params(**{"1": tid, "2": "test-tenant", "3": f"test-tenant-{tid}"}),
            )

            # 2. Create server (referenced by installation)
            server_id = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO servers (id, tenant_id, hostname, ip_address, created_at) "
                    "VALUES (:1, :2, :3, :4, now()) ON CONFLICT DO NOTHING"
                ),
                _params(**{"1": server_id, "2": tid, "3": "test-host", "4": "10.0.0.1"}),
            )

            # 3. Create installation (references server)
            inst_id = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO agent_installations (id, server_id, tenant_id, "
                    "host_fingerprint, agent_type, agent_version, capabilities_json, "
                    "status, created_at, updated_at) "
                    "VALUES (:1, :2, :3, :4, :5, :6, :7, :8, now(), now()) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                _params(**{
                    "1": inst_id,
                    "2": server_id,
                    "3": tid,
                    "4": str(uuid.uuid4()),
                    "5": "agent-type",
                    "6": "1.0.0",
                    "7": "{}",
                    "8": "ACTIVE",
                }),
            )

            # 4. Create credential (references installation)
            cred_id = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO agent_credentials (id, installation_id, tenant_id, status) "
                    "VALUES (:1, :2, :3, :4) ON CONFLICT (id) DO NOTHING"
                ),
                _params(**{"1": cred_id, "2": inst_id, "3": tid, "4": "ACTIVE"}),
            )

            # 5. Create instance (references installation and credential)
            instance_id = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO agent_instances (id, installation_id, credential_id, "
                    "tenant_id, host_fingerprint, status) "
                    "VALUES (:1, :2, :3, :4, :5, :6) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                _params(**{
                    "1": instance_id,
                    "2": inst_id,
                    "3": cred_id,
                    "4": tid,
                    "5": str(uuid.uuid4()),
                    "6": status,
                }),
            )

            # Reset sequences so subsequent INSERTs use correct IDs
            await conn.execute(
                text(
                    "SELECT setval('agent_installations_id_seq', "
                    "(SELECT MAX(id) FROM agent_installations))"
                )
            )
            await conn.execute(
                text(
                    "SELECT setval('agent_credentials_id_seq', "
                    "(SELECT MAX(id) FROM agent_credentials))"
                )
            )
            await conn.execute(
                text(
                    "SELECT setval('agent_instances_id_seq', "
                    "(SELECT MAX(id) FROM agent_instances))"
                )
            )

        # Fetch installed records for return
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT id, server_id, tenant_id, status "
                    "FROM agent_installations WHERE id = :1"
                ),
                _params(**{"1": inst_id}),
            )
            instl = dict(result.mappings().one())

            result2 = await conn.execute(
                text("SELECT id, status FROM agent_credentials WHERE id = :1"),
                _params(**{"1": cred_id}),
            )
            cred = dict(result2.mappings().one())

            result3 = await conn.execute(
                text(
                    "SELECT id, status, installation_id, credential_id, tenant_id "
                    "FROM agent_instances WHERE id = :1"
                ),
                _params(**{"1": instance_id}),
            )
            inst = dict(result3.mappings().one())

        return inst, cred, instl

    return _create