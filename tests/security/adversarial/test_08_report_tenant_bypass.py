"""08 - Report Tenant Bypass: normal user cannot generate reports for other tenants.

Enforces: P1 (tenant isolation), ReportService tenant scoping.
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from libs.access.rbac import ROLE_ADMIN, ROLE_SUPERADMIN, ROLE_VIEWER
from libs.access.security import JwtService
from libs.access.tenant_scope import AuthorizationContext

SECRET = "test-secret"
TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


def _token(jwt, role, tenant_id):
    return jwt.create_access_token(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        email="user@test.com",
        role=role,
    )


def test_viewer_cannot_generate_for_other_tenant(jwt):
    """Viewer from tenant A cannot generate reports for tenant B."""
    from libs.access.rbac import cross_tenant_allowed

    token = jwt.verify_access_token(_token(jwt, ROLE_VIEWER, TENANT_A))
    assert not cross_tenant_allowed(token.role)


def test_admin_cannot_generate_for_other_tenant(jwt):
    """Admin from tenant A cannot generate reports for tenant B."""
    from libs.access.rbac import cross_tenant_allowed

    token = jwt.verify_access_token(_token(jwt, ROLE_ADMIN, TENANT_A))
    assert not cross_tenant_allowed(token.role)


def test_superadmin_can_generate_for_other_tenant(jwt):
    """Superadmin CAN generate reports for any tenant."""
    from libs.access.rbac import cross_tenant_allowed

    token = jwt.verify_access_token(_token(jwt, ROLE_SUPERADMIN, TENANT_A))
    assert cross_tenant_allowed(token.role)


def test_viewer_own_tenant_allowed(jwt):
    """Viewer can access their own tenant (same-tenant always allowed)."""
    token = jwt.verify_access_token(_token(jwt, ROLE_VIEWER, TENANT_A))
    ctx = AuthorizationContext.from_token_payload(token)
    effective = ctx.resolve(TENANT_A)
    assert effective == TENANT_A
