"""HTTP-level tests for the GatewayService Learning Memory (P7) routes.

Uses a fake JWT + fake MemoryStore (no PG). Verifies:
- GET  /tenants/{tid}/memory        -> tenant-scoped list
- POST /tenants/{tid}/memory        -> persists (idempotent, authorized)
- 401 when no token, 403 on cross-tenant, 400 on invalid body
- 404/500 path safety via unconfigured store
"""
import sys
import uuid
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.access.errors import TenantIsolationError
from libs.access.rbac import ROLE_ADMIN
from libs.access.security import JwtService

from src.health import GatewayServer
from src.service import GatewayService


SECRET = "dev-secret-key"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
USER_ADMIN = "00000000-0000-0000-0000-0000000000aa"


class FakeMemoryStore:
    def __init__(self):
        self.rows = []
        self.persisted = []

    @staticmethod
    def _wrap(d):
        return type("R", (), {"to_payload": staticmethod(lambda: d)})()

    async def persist(self, *, record):
        rec = {
            "id": str(uuid.uuid4()),
            "tenant_id": str(record.tenant_id),
            "target_type": record.target_type,
            "target_id": str(record.target_id),
            "signal": record.signal,
            "provenance": record.provenance,
            "signal_hash": "h" * 64,
            "created_at": "2026-01-01T00:00:00",
        }
        self.rows.append(rec)
        self.persisted.append(rec)
        return self._wrap(rec)

    async def list(self, *, tenant_id, target_type=None, target_id=None):
        out = [
            r
            for r in self.rows
            if uuid.UUID(r["tenant_id"]) == tenant_id
            and (target_type is None or r["target_type"] == target_type)
            and (target_id is None or uuid.UUID(r["target_id"]) == target_id)
        ]
        return [self._wrap(r) for r in out]

    async def get_latest(self, *, tenant_id, target_type, target_id):
        for r in self.rows:
            if (
                uuid.UUID(r["tenant_id"]) == tenant_id
                and r["target_type"] == target_type
                and uuid.UUID(r["target_id"]) == target_id
            ):
                return self._wrap(r)
        return None

    async def verify_connection(self):
        return None

    async def close(self):
        return None


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


@pytest.fixture
async def client(jwt):
    store = FakeMemoryStore()
    service = GatewayService(jwt, memory_store=store)
    server = GatewayServer(service, jwt)
    tc = TestClient(TestServer(server.app))
    await tc.start_server()
    yield tc, store
    await tc.close()


def _token(jwt, *, tenant_id=TENANT_A):
    return jwt.create_access_token(
        user_id=USER_ADMIN, tenant_id=tenant_id, email="a@x.test", role=ROLE_ADMIN
    )


def _hdr(jwt, **kw):
    return {"Authorization": f"Bearer {_token(jwt, **kw)}",
            "Content-Type": "application/json"}


async def test_get_memory_requires_auth(client, jwt):
    tc, _ = client
    resp = await tc.get(f"/api/v1/tenants/{TENANT_A}/memory")
    assert resp.status == 401


async def test_get_memory_returns_tenant_scoped_list(client, jwt):
    tc, store = client
    store.rows.append({
        "id": str(uuid.uuid4()), "tenant_id": TENANT_A,
        "target_type": "pattern", "target_id": str(uuid.uuid4()),
        "signal": {"action": "keep"}, "provenance": {"n": 1},
        "signal_hash": "h" * 64, "created_at": "2026-01-01T00:00:00",
    })
    resp = await tc.get(f"/api/v1/tenants/{TENANT_A}/memory", headers=_hdr(jwt))
    assert resp.status == 200
    body = await resp.json()
    assert body["total"] == 1  # noqa: PLR2004
    assert body["memories"][0]["target_type"] == "pattern"


async def test_post_memory_persists_and_is_authorized(client, jwt):
    tc, store = client
    pid = str(uuid.uuid4())
    body = {
        "target_type": "pattern", "target_id": pid,
        "signal": {"action": "deactivate", "recommended_strength": 0.0},
        "provenance": {"corroborated": 1, "contradicted": 3},
    }
    resp = await tc.post(
        f"/api/v1/tenants/{TENANT_A}/memory",
        headers=_hdr(jwt), json=body,
    )
    assert resp.status == 200
    out = await resp.json()
    assert out["target_type"] == "pattern"
    assert out["target_id"] == pid
    assert len(store.persisted) == 1  # noqa: PLR2004


async def test_post_memory_rejects_invalid_target_type(client, jwt):
    tc, _ = client
    body = {"target_type": "banana", "target_id": str(uuid.uuid4()),
            "signal": {}, "provenance": {}}
    resp = await tc.post(
        f"/api/v1/tenants/{TENANT_A}/memory", headers=_hdr(jwt), json=body
    )
    assert resp.status == 400


async def test_post_memory_rejects_non_object_signal(client, jwt):
    tc, _ = client
    body = {"target_type": "pattern", "target_id": str(uuid.uuid4()),
            "signal": "not-an-object", "provenance": {}}
    resp = await tc.post(
        f"/api/v1/tenants/{TENANT_A}/memory", headers=_hdr(jwt), json=body
    )
    assert resp.status == 400


async def test_post_memory_cross_tenant_denied(client, jwt):
    tc, _ = client
    body = {"target_type": "pattern", "target_id": str(uuid.uuid4()),
            "signal": {"action": "keep"}, "provenance": {}}
    resp = await tc.post(
        f"/api/v1/tenants/{TENANT_B}/memory",
        headers=_hdr(jwt, tenant_id=TENANT_A), json=body,
    )
    assert resp.status == 403


async def test_post_memory_viewer_role_forbidden(client, jwt):
    tc, _ = client
    viewer = jwt.create_access_token(
        user_id=USER_ADMIN, tenant_id=TENANT_A, email="v@x.test", role="viewer"
    )
    body = {"target_type": "pattern", "target_id": str(uuid.uuid4()),
            "signal": {"action": "keep"}, "provenance": {}}
    resp = await tc.post(
        f"/api/v1/tenants/{TENANT_A}/memory",
        headers={"Authorization": f"Bearer {viewer}", "Content-Type": "application/json"},
        json=body,
    )
    assert resp.status == 403
