"""Unit tests for the GatewayService Context Revision (P7 + P2) read path.

Uses a fake JWT + fake ContextRevisionStore (no PG). Verifies:
- tenant-scoped read via get_context_revision
- cross-tenant isolation (admin cannot read another tenant -> error path)
- response is a JSON-serializable tenant-scoped report
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.access.errors import TenantIsolationError
from libs.access.rbac import ROLE_ADMIN
from libs.access.security import JwtService
from libs.memory.context_revision import ContextRevisionReport

from src.service import GatewayService

SECRET = "dev-secret-key"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
USER_ADMIN = "00000000-0000-0000-0000-0000000000aa"


class FakeContextRevisionStore:
    def __init__(self, report):
        self._report = report
        self.calls = []

    async def revise_for_tenant(self, *, tenant_id: uuid.UUID) -> ContextRevisionReport:
        self.calls.append(tenant_id)
        return self._report

    async def verify_connection(self):
        return None


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


@pytest.fixture
def service(jwt):
    report = ContextRevisionReport(
        tenant_id=uuid.UUID(TENANT_A),
        total_contexts=0,
        contexts_with_outcomes=0,
        results=[],
    )
    return GatewayService(jwt, context_revision_store=FakeContextRevisionStore(report))


def _token(jwt, *, tenant_id=TENANT_A):
    return jwt.create_access_token(
        user_id=USER_ADMIN, tenant_id=tenant_id, email="a@x.test", role=ROLE_ADMIN
    )


async def test_get_context_revision_returns_tenant_scoped_report(service, jwt):
    token = jwt.verify_access_token(_token(jwt))
    result = await service.get_context_revision(token, TENANT_A)
    assert result["tenant_id"] == TENANT_A
    assert result["total_contexts"] == 0
    assert isinstance(result["tenant_id"], str)


async def test_get_context_revision_cross_tenant_admin_denied(service, jwt):
    token = jwt.verify_access_token(_token(jwt, tenant_id=TENANT_A))
    with pytest.raises(TenantIsolationError):
        await service.get_context_revision(token, TENANT_B)


async def test_get_context_revision_unconfigured_store_raises(service, jwt):
    bare = GatewayService(jwt, context_revision_store=None)
    token = jwt.verify_access_token(_token(jwt))
    with pytest.raises(RuntimeError):
        await bare.get_context_revision(token, TENANT_A)
