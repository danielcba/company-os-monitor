"""Unit tests for the Decision Authority RBAC matrix (external, ADR-0002).

The matrix (docs/04 decision_authority.yaml) is asserted CELL BY CELL so a
regression in one role/permission is caught by its dedicated assertion:
viewer NEVER propose/commit/execute; operator NEVER propose/commit; admin
commits low/medium (tenant scope); superadmin commits high + cross-tenant.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.access.errors import InvalidRoleError
from libs.access.rbac import (
    PERM_ACK,
    PERM_COMMIT,
    PERM_CROSS_TENANT,
    PERM_DEFINE_POLICY,
    PERM_EXECUTE,
    PERM_PROPOSE,
    PERM_READ,
    PERMISSIONS,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_TOLERANCES,
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_SUPERADMIN,
    ROLE_VIEWER,
    ROLES,
    ack_allowed,
    can,
    commit_allowed,
    commit_risk_allowed,
    cross_tenant_allowed,
    define_policy_allowed,
    execute_allowed,
    permissions_for,
    propose_allowed,
    read_allowed,
    tenant_scope,
)


def test_declared_roles_and_permissions_sets():
    assert ROLES == {ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN, ROLE_SUPERADMIN}
    assert PERMISSIONS == {
        PERM_READ,
        PERM_PROPOSE,
        PERM_ACK,
        PERM_COMMIT,
        PERM_EXECUTE,
        PERM_DEFINE_POLICY,
        PERM_CROSS_TENANT,
    }
    assert RISK_TOLERANCES == {RISK_LOW, RISK_MEDIUM, RISK_HIGH}


def test_unknown_role_and_permission_fail_loudly():
    with pytest.raises(InvalidRoleError):
        can("ghost", PERM_READ)
    with pytest.raises(ValueError):
        can(ROLE_ADMIN, "not-a-permission")


def test_viewer_matrix():
    assert read_allowed(ROLE_VIEWER)
    assert not propose_allowed(ROLE_VIEWER)
    assert not ack_allowed(ROLE_VIEWER)
    assert not commit_allowed(ROLE_VIEWER)
    assert not commit_allowed(ROLE_VIEWER, RISK_LOW)
    assert not execute_allowed(ROLE_VIEWER)
    assert not define_policy_allowed(ROLE_VIEWER)
    assert not cross_tenant_allowed(ROLE_VIEWER)
    assert permissions_for(ROLE_VIEWER) == frozenset({PERM_READ})


def test_operator_matrix():
    assert read_allowed(ROLE_OPERATOR)
    assert ack_allowed(ROLE_OPERATOR)
    assert not propose_allowed(ROLE_OPERATOR)
    assert not commit_allowed(ROLE_OPERATOR)
    assert not commit_allowed(ROLE_OPERATOR, RISK_MEDIUM)
    assert not execute_allowed(ROLE_OPERATOR)
    assert not cross_tenant_allowed(ROLE_OPERATOR)
    assert permissions_for(ROLE_OPERATOR) == frozenset({PERM_READ, PERM_ACK})


def test_admin_matrix():
    assert read_allowed(ROLE_ADMIN)
    assert propose_allowed(ROLE_ADMIN)
    assert ack_allowed(ROLE_ADMIN)
    assert commit_allowed(ROLE_ADMIN)
    assert commit_risk_allowed(ROLE_ADMIN, RISK_LOW)
    assert commit_risk_allowed(ROLE_ADMIN, RISK_MEDIUM)
    assert not commit_risk_allowed(ROLE_ADMIN, RISK_HIGH)
    assert not commit_allowed(ROLE_ADMIN, RISK_HIGH)
    assert not execute_allowed(ROLE_ADMIN)
    assert define_policy_allowed(ROLE_ADMIN)
    assert not cross_tenant_allowed(ROLE_ADMIN)
    assert permissions_for(ROLE_ADMIN) == frozenset(
        {PERM_READ, PERM_PROPOSE, PERM_ACK, PERM_COMMIT, PERM_DEFINE_POLICY}
    )


def test_superadmin_matrix():
    assert read_allowed(ROLE_SUPERADMIN)
    assert propose_allowed(ROLE_SUPERADMIN)
    assert ack_allowed(ROLE_SUPERADMIN)
    assert commit_allowed(ROLE_SUPERADMIN)
    assert commit_risk_allowed(ROLE_SUPERADMIN, RISK_HIGH)
    assert commit_allowed(ROLE_SUPERADMIN, RISK_HIGH)
    assert execute_allowed(ROLE_SUPERADMIN)
    assert define_policy_allowed(ROLE_SUPERADMIN)
    assert cross_tenant_allowed(ROLE_SUPERADMIN)
    assert permissions_for(ROLE_SUPERADMIN) == frozenset(
        {
            PERM_READ,
            PERM_PROPOSE,
            PERM_ACK,
            PERM_COMMIT,
            PERM_EXECUTE,
            PERM_DEFINE_POLICY,
            PERM_CROSS_TENANT,
        }
    )


def test_tenant_scope_defaults_to_actor_tenant():
    assert tenant_scope(ROLE_VIEWER, "t1", None) == "t1"
    assert tenant_scope(ROLE_ADMIN, "t1", "t1") == "t1"


def test_tenant_scope_superadmin_may_cross_tenant():
    assert tenant_scope(ROLE_SUPERADMIN, "t1", "t2") == "t2"


def test_tenant_scope_non_superadmin_cross_tenant_raises():
    from libs.access.errors import TenantIsolationError

    for role in (ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN):
        with pytest.raises(TenantIsolationError):
            tenant_scope(role, "t1", "t2")


def test_commit_risk_unknown_risk_raises():
    with pytest.raises(ValueError):
        commit_risk_allowed(ROLE_ADMIN, "extreme")