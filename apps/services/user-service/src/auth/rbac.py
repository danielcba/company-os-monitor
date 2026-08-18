"""RBAC facade - Decision Authority roles and permission checks (external).

Re-exports the shared Decision Authority model from ``libs.access.rbac``
(roles viewer/operator/admin/superadmin mapped to commitment authority per
docs/04; pure constants and pure functions, tested) plus a service-side helper
that validates a role string before persisting a user.
"""
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

__all__ = [
    "PERMISSIONS",
    "PERM_ACK",
    "PERM_COMMIT",
    "PERM_CROSS_TENANT",
    "PERM_DEFINE_POLICY",
    "PERM_EXECUTE",
    "PERM_PROPOSE",
    "PERM_READ",
    "RISK_HIGH",
    "RISK_LOW",
    "RISK_MEDIUM",
    "RISK_TOLERANCES",
    "ROLES",
    "ROLE_ADMIN",
    "ROLE_OPERATOR",
    "ROLE_SUPERADMIN",
    "ROLE_VIEWER",
    "ack_allowed",
    "can",
    "commit_allowed",
    "commit_risk_allowed",
    "cross_tenant_allowed",
    "define_policy_allowed",
    "execute_allowed",
    "permissions_for",
    "propose_allowed",
    "read_allowed",
    "tenant_scope",
    "validate_role",
]


def validate_role(role: str) -> None:
    """Fail loudly on roles that are not declared Decision Authority roles."""
    if role not in ROLES:
        raise InvalidRoleError(
            f"unknown Decision Authority role: {role!r} "
            f"(declared roles: {sorted(ROLES)})"
        )