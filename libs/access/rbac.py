"""Decision Authority RBAC - roles and permissions (external, ADR-0002).

The RBAC maps to the **Decision Authority** of the Decision concept (the
commitment authority under which a Decision is taken, core-concepts/decision.md).
Per docs/04 this is NOT a permission table: it is an authority-binding model.
Each role is a declared Decision Authority; ``can``/``commit_allowed``/
``cross_tenant_allowed`` decide whether that authority may execute a given
action on the canonical flow. Pure constants and pure functions, fully tested.

Roles (docs/04 decision_authority.yaml):

- viewer:     READ Active Context / Recommendations / Decisions / Reports.
              NO propose, NO commit, NO execute.
- operator:   all viewer + ACK a Decision. NO propose, NO commit.
- admin:      all operator + PROPOSE (tenant scope) + COMMIT (tenant scope,
              risk_tolerance low/medium) + define automated policies.
- superadmin: all admin + COMMIT (cross-tenant, risk_tolerance high) +
              DEFINE policies / action space / tolerance thresholds + EXECUTE.

This module never reasons: it only classifies authority (R1 external contract).
"""
from libs.access.errors import InvalidRoleError, TenantIsolationError

# Declared Decision Authority roles.
ROLE_VIEWER = "viewer"
ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"
ROLE_SUPERADMIN = "superadmin"
ROLES: frozenset[str] = frozenset(
    {ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN, ROLE_SUPERADMIN}
)

# Actions (permissions) on the canonical flow.
PERM_READ = "read"  # read contexts / recommendations / decisions / reports
PERM_PROPOSE = "propose"  # propose a Recommendation
PERM_ACK = "ack"  # acknowledge a Decision (confirm execution started)
PERM_COMMIT = "commit"  # commit a Decision (Action - Commit)
PERM_EXECUTE = "execute"  # execute a committed action
PERM_DEFINE_POLICY = "define_policy"  # define automated policies / action space
PERM_CROSS_TENANT = "cross_tenant"  # operate across tenant boundaries
PERMISSIONS: frozenset[str] = frozenset(
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

# Declared risk tolerance levels (Action - Commit, docs/03).
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_TOLERANCES: frozenset[str] = frozenset({RISK_LOW, RISK_MEDIUM, RISK_HIGH})

# Declarative role -> permissions matrix (docs/04 decision_authority.yaml).
_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    ROLE_VIEWER: frozenset({PERM_READ}),
    ROLE_OPERATOR: frozenset({PERM_READ, PERM_ACK}),
    ROLE_ADMIN: frozenset(
        {PERM_READ, PERM_PROPOSE, PERM_ACK, PERM_COMMIT, PERM_DEFINE_POLICY}
    ),
    ROLE_SUPERADMIN: frozenset(
        {
            PERM_READ,
            PERM_PROPOSE,
            PERM_ACK,
            PERM_COMMIT,
            PERM_EXECUTE,
            PERM_DEFINE_POLICY,
            PERM_CROSS_TENANT,
        }
    ),
}

# Risk tolerance ceiling per role for COMMIT (docs/04: admin low/medium in
# tenant scope; superadmin also high and cross-tenant).
_COMMIT_RISK_CEILING: dict[str, frozenset[str]] = {
    ROLE_ADMIN: frozenset({RISK_LOW, RISK_MEDIUM}),
    ROLE_SUPERADMIN: frozenset({RISK_LOW, RISK_MEDIUM, RISK_HIGH}),
}


def _require_valid_role(role: str) -> None:
    if role not in ROLES:
        raise InvalidRoleError(  # noqa: TRY003 - declarative error, one message
            f"unknown Decision Authority role: {role!r} "
            f"(declared roles: {sorted(ROLES)})"
        )


def permissions_for(role: str) -> frozenset[str]:
    """The declared permissions of a role (raises on unknown role)."""
    _require_valid_role(role)
    return _ROLE_PERMISSIONS[role]


def can(role: str, permission: str) -> bool:
    """Whether the role holds a given permission (pure, no I/O)."""
    _require_valid_role(role)
    if permission not in PERMISSIONS:
        raise ValueError(f"unknown permission: {permission!r}")  # noqa: TRY003
    return permission in _ROLE_PERMISSIONS[role]


def read_allowed(role: str) -> bool:
    return can(role, PERM_READ)


def propose_allowed(role: str) -> bool:
    return can(role, PERM_PROPOSE)


def ack_allowed(role: str) -> bool:
    return can(role, PERM_ACK)


def define_policy_allowed(role: str) -> bool:
    return can(role, PERM_DEFINE_POLICY)


def execute_allowed(role: str) -> bool:
    return can(role, PERM_EXECUTE)


def cross_tenant_allowed(role: str) -> bool:
    """Only superadmin holds cross-tenant authority (docs/04)."""
    return can(role, PERM_CROSS_TENANT)


def commit_risk_allowed(role: str, risk: str) -> bool:
    """Whether the role may COMMIT a Decision at the given risk tolerance.

    admin: low/medium within its tenant; superadmin: low/medium/high
    (including cross-tenant). viewer/operator never commit.
    """
    _require_valid_role(role)
    if risk not in RISK_TOLERANCES:
        raise ValueError(f"unknown risk tolerance: {risk!r}")  # noqa: TRY003
    return risk in _COMMIT_RISK_CEILING.get(role, frozenset())


def commit_allowed(role: str, risk: str | None = None) -> bool:
    """Whether the role may COMMIT, optionally constrained by risk tolerance."""
    if not can(role, PERM_COMMIT):
        return False
    if risk is None:
        return True
    return commit_risk_allowed(role, risk)


def tenant_scope(role: str, actor_tenant_id: str, requested_tenant_id: str | None):
    """Resolve the effective tenant scope of an action.

    A role acts inside its own tenant unless it holds cross-tenant authority
    (superadmin) and the request explicitly names another tenant. Returns the
    effective tenant id; raises TenantIsolationError on cross-tenant attempts
    without that authority (multi-tenant isolation).
    """
    _require_valid_role(role)
    target = str(requested_tenant_id) if requested_tenant_id else str(actor_tenant_id)
    if str(target) != str(actor_tenant_id) and not cross_tenant_allowed(role):
        raise TenantIsolationError(  # noqa: TRY003 - declarative, one message
            "cross-tenant access requires superadmin authority "
            "(cross_tenant permission)"
        )
    return target