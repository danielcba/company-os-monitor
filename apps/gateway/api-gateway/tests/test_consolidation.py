"""Unit tests for the GatewayService Memory (P7) consolidation read path.

Uses a fake JWT + fake ConsolidationStore (no PG). Verifies:
- tenant-scoped read via get_consolidation
- cross-tenant isolation (admin cannot read another tenant -> 403 path)
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
from libs.memory.consolidation import ConsolidationReport

from src.service import GatewayService

SECRET = "dev-secret-key"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
USER_ADMIN = "00000000-0000-0000-0000-0000000000aa"


class FakeConsolidationStore:
    def __init__(self, report):
        self._report = report
        self.calls = []

    async def consolidate_for_tenant(self, *, tenant_id: uuid.UUID) -> ConsolidationReport:
        self.calls.append(tenant_id)
        return self._report

    async def verify_connection(self):
        return None


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


@pytest.fixture
def service(jwt):
    report = ConsolidationReport(
        tenant_id=uuid.UUID(TENANT_A),
        total_decisions=0,
        decisions_with_actuals=0,
        corroborated=0,
        contradicted=0,
        inconclusive=0,
        aggregate_feedback=0.0,
        results=[],
    )
    return GatewayService(jwt, consolidation_store=FakeConsolidationStore(report))


def _token(jwt, *, tenant_id=TENANT_A):
    return jwt.create_access_token(
        user_id=USER_ADMIN, tenant_id=tenant_id, email="a@x.test", role=ROLE_ADMIN
    )


async def test_get_consolidation_returns_tenant_scoped_report(service, jwt):
    token = jwt.verify_access_token(_token(jwt))
    result = await service.get_consolidation(token, TENANT_A)
    assert result["tenant_id"] == TENANT_A
    assert result["total_decisions"] == 0
    # JSON-serializable (UUID -> str)
    assert isinstance(result["tenant_id"], str)


async def test_get_consolidation_cross_tenant_admin_denied(service, jwt):
    token = jwt.verify_access_token(_token(jwt, tenant_id=TENANT_A))
    with pytest.raises(TenantIsolationError):
        await service.get_consolidation(token, TENANT_B)


async def test_get_consolidation_unconfigured_store_raises(service, jwt):
    bare = GatewayService(jwt, consolidation_store=None)
    token = jwt.verify_access_token(_token(jwt))
    with pytest.raises(RuntimeError):
        await bare.get_consolidation(token, TENANT_A)
