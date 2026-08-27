"""Unit tests for the GatewayService Insight Transformation (R6) read path.

Uses a fake JWT + fake InsightTransformationStore (no PG). Verifies:
- tenant-scoped read via get_insight_transformation
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
from libs.memory.insight_transformation import InsightTransformationReport

from src.service import GatewayService

SECRET = "dev-secret-key"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
USER_ADMIN = "00000000-0000-0000-0000-0000000000aa"


class FakeInsightTransformationStore:
    def __init__(self, report):
        self._report = report
        self.calls = []

    async def journal_for_tenant(self, *, tenant_id: uuid.UUID) -> InsightTransformationReport:
        self.calls.append(tenant_id)
        return self._report

    async def verify_connection(self):
        return None


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


@pytest.fixture
def service(jwt):
    report = InsightTransformationReport(
        tenant_id=uuid.UUID(TENANT_A),
        total_insights=0,
        results=[],
    )
    return GatewayService(jwt, insight_transformation_store=FakeInsightTransformationStore(report))


def _token(jwt, *, tenant_id=TENANT_A):
    return jwt.create_access_token(
        user_id=USER_ADMIN, tenant_id=tenant_id, email="a@x.test", role=ROLE_ADMIN
    )


async def test_get_insight_transformation_returns_tenant_scoped_report(service, jwt):
    token = jwt.verify_access_token(_token(jwt))
    result = await service.get_insight_transformation(token, TENANT_A)
    assert result["tenant_id"] == TENANT_A
    assert result["total_insights"] == 0
    assert isinstance(result["tenant_id"], str)


async def test_get_insight_transformation_cross_tenant_admin_denied(service, jwt):
    token = jwt.verify_access_token(_token(jwt, tenant_id=TENANT_A))
    with pytest.raises(TenantIsolationError):
        await service.get_insight_transformation(token, TENANT_B)


async def test_get_insight_transformation_unconfigured_store_raises(service, jwt):
    bare = GatewayService(jwt, insight_transformation_store=None)
    token = jwt.verify_access_token(_token(jwt))
    with pytest.raises(RuntimeError):
        await bare.get_insight_transformation(token, TENANT_A)
