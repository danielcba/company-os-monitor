"""HTTP-level tests for the GatewayService Cognitive Timeline route.

Uses a fake JWT + fake Timeline store (no PG). Verifies:
- GET  /tenants/{tid}/cognitive-timeline -> 200 tenant-scoped reconstruction
- 401 when no token, 403 on cross-tenant
"""
import sys
import uuid
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.access.rbac import ROLE_ADMIN
from libs.access.security import JwtService
from libs.memory.cognitive_timeline import CognitiveTimelineReport, TimelineEvent

from src.health import GatewayServer
from src.service import GatewayService

SECRET = "dev-secret-key"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
USER_ADMIN = "00000000-0000-0000-0000-0000000000aa"


class FakeTimelineStore:
    def __init__(self):
        self.calls = []

    async def build_for_tenant(
        self, *, tenant_id: uuid.UUID, limit_per_concept: int = 20, ascending: bool = False
    ) -> CognitiveTimelineReport:
        self.calls.append((tenant_id, limit_per_concept, ascending))
        return CognitiveTimelineReport(
            tenant_id=tenant_id,
            events=[
                TimelineEvent(
                    tenant_id=tenant_id,
                    layer="perception",
                    concept="observation",
                    id="o1",
                    timestamp="2026-01-01T00:00:00",
                    title="Observation: cpu",
                    detail="90 %",
                )
            ],
            total=1,
            per_layer_counts={"perception": 1},
            per_concept_counts={"observation": 1},
            ascending=ascending,
        )

    async def verify_connection(self):
        return None

    async def close(self):
        return None


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


@pytest.fixture
async def client(jwt):
    store = FakeTimelineStore()
    service = GatewayService(jwt, timeline_store=store)
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
    return {"Authorization": f"Bearer {_token(jwt, **kw)}"}


async def test_timeline_requires_auth(client, jwt):
    tc, _ = client
    resp = await tc.get(f"/api/v1/tenants/{TENANT_A}/cognitive-timeline")
    assert resp.status == 401


async def test_timeline_returns_reconstruction(client, jwt):
    tc, store = client
    resp = await tc.get(
        f"/api/v1/tenants/{TENANT_A}/cognitive-timeline", headers=_hdr(jwt)
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["total"] == 1
    assert body["events"][0]["concept"] == "observation"
    assert store.calls[0][0] == uuid.UUID(TENANT_A)


async def test_timeline_cross_tenant_denied(client, jwt):
    tc, _ = client
    resp = await tc.get(
        f"/api/v1/tenants/{TENANT_B}/cognitive-timeline",
        headers=_hdr(jwt, tenant_id=TENANT_A),
    )
    assert resp.status == 403
