"""Unit tests for AuthorizationContext (Phase 1 — Multi-Tenant Security).

Tests the centralized tenant scope resolution logic that every handler
must use. No I/O — pure unit tests with fake token payloads.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.access.errors import TenantIsolationError
from libs.access.rbac import ROLE_ADMIN, ROLE_SUPERADMIN, ROLE_VIEWER
from libs.access.security import JwtService
from libs.access.tenant_scope import AuthorizationContext

SECRET = "test-secret"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"


class FakePayload:
    """Minimal token payload for testing without JWT."""

    def __init__(self, *, user_id, tenant_id, role):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


def test_from_token_payload_copies_identity():
    payload = FakePayload(user_id="u1", tenant_id=TENANT_A, role=ROLE_VIEWER)
    ctx = AuthorizationContext.from_token_payload(payload)
    assert ctx.user_id == "u1"
    assert ctx.tenant_id == TENANT_A
    assert ctx.role == ROLE_VIEWER
    assert ctx.effective_tenant_id == TENANT_A


def test_resolve_no_requested_tenant_returns_own():
    payload = FakePayload(user_id="u1", tenant_id=TENANT_A, role=ROLE_VIEWER)
    ctx = AuthorizationContext.from_token_payload(payload)
    assert ctx.resolve() == TENANT_A


def test_resolve_same_tenant_always_allowed():
    payload = FakePayload(user_id="u1", tenant_id=TENANT_A, role=ROLE_VIEWER)
    ctx = AuthorizationContext.from_token_payload(payload)
    assert ctx.resolve(TENANT_A) == TENANT_A


def test_resolve_cross_tenant_viewer_denied():
    payload = FakePayload(user_id="u1", tenant_id=TENANT_A, role=ROLE_VIEWER)
    ctx = AuthorizationContext.from_token_payload(payload)
    with pytest.raises(TenantIsolationError):
        ctx.resolve(TENANT_B)


def test_resolve_cross_tenant_admin_denied():
    payload = FakePayload(user_id="u1", tenant_id=TENANT_A, role=ROLE_ADMIN)
    ctx = AuthorizationContext.from_token_payload(payload)
    with pytest.raises(TenantIsolationError):
        ctx.resolve(TENANT_B)


def test_resolve_cross_tenant_superadmin_allowed():
    payload = FakePayload(user_id="u1", tenant_id=TENANT_A, role=ROLE_SUPERADMIN)
    ctx = AuthorizationContext.from_token_payload(payload)
    assert ctx.resolve(TENANT_B) == TENANT_B


def test_validate_same_tenant_passes():
    payload = FakePayload(user_id="u1", tenant_id=TENANT_A, role=ROLE_VIEWER)
    ctx = AuthorizationContext.from_token_payload(payload)
    ctx.validate_same_tenant(TENANT_A)  # should not raise


def test_validate_same_tenant_fails():
    payload = FakePayload(user_id="u1", tenant_id=TENANT_A, role=ROLE_VIEWER)
    ctx = AuthorizationContext.from_token_payload(payload)
    with pytest.raises(TenantIsolationError):
        ctx.validate_same_tenant(TENANT_B)


def test_effective_tenant_mutable_after_creation():
    """effective_tenant_id can be set by _resolve_tenant in GatewayService."""
    payload = FakePayload(user_id="u1", tenant_id=TENANT_A, role=ROLE_SUPERADMIN)
    ctx = AuthorizationContext.from_token_payload(payload)
    # Simulate what GatewayService._resolve_tenant does:
    ctx.effective_tenant_id = ctx.resolve(TENANT_B)
    assert ctx.effective_tenant_id == TENANT_B
