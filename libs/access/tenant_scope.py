"""Centralized tenant scope resolution (external, ADR-0002).

Provides ``AuthorizationContext`` — a single point of truth for resolving
the effective tenant scope of an authenticated request. Every handler that
accesses tenant-scoped data MUST go through this abstraction instead of
duplicating tenant isolation logic across 20 call sites.

The token's ``tenant_id`` is the source of truth. The client may request a
different ``requested_tenant_id``; cross-tenant access requires the
``cross_tenant`` permission (superadmin only). This module NEVER produces
cognitive judgments (R1 for the external layer): it only resolves authority.

Usage::

    from libs.access.tenant_scope import AuthorizationContext, TenantScopeError

    ctx = AuthorizationContext.from_token_payload(token_payload)
    effective = ctx.resolve(requested_tenant_id="...")
"""
from __future__ import annotations

from dataclasses import dataclass

from libs.access.errors import TenantIsolationError
from libs.access.rbac import cross_tenant_allowed


class TenantScopeError(TenantIsolationError):
    """Raised when tenant scope resolution fails."""


@dataclass
class AuthorizationContext:
    """Resolved authority and scope for an authenticated request.

    Attributes:
        user_id: The authenticated user's ID.
        tenant_id: The token's tenant scope (source of truth).
        role: The user's Decision Authority role.
        effective_tenant_id: The resolved tenant (token tenant or cross-tenant target).
    """

    user_id: str
    tenant_id: str
    role: str
    effective_tenant_id: str

    @classmethod
    def from_token_payload(cls, payload) -> AuthorizationContext:
        """Create from a verified TokenPayload (never from client input)."""
        return cls(
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            role=payload.role,
            effective_tenant_id=payload.tenant_id,
        )

    def resolve(self, requested_tenant_id: str | None = None) -> str:
        """Resolve the effective tenant for a request.

        Args:
            requested_tenant_id: The tenant the client wants to access.
                If None, returns the token's own tenant.

        Returns:
            The effective tenant_id as a string.

        Raises:
            TenantScopeError: If cross-tenant access is not authorized.
        """
        if requested_tenant_id is None:
            return self.effective_tenant_id

        target = str(requested_tenant_id)

        # Same tenant — always allowed.
        if target == self.tenant_id:
            return target

        # Cross-tenant — requires superadmin authority.
        if not cross_tenant_allowed(self.role):
            raise TenantScopeError(  # noqa: TRY003 - declarative error
                f"cross-tenant access requires superadmin authority; "
                f"role={self.role!r} token_tenant={self.tenant_id!r} "
                f"requested_tenant={target!r}"
            )

        return target

    def validate_same_tenant(self, resource_tenant_id: str) -> None:
        """Validate that a resource belongs to the effective tenant.

        Raises:
            TenantScopeError: If the resource is in a different tenant.
        """
        if str(resource_tenant_id) != self.effective_tenant_id:
            raise TenantScopeError(  # noqa: TRY003 - declarative error
                f"resource tenant {resource_tenant_id!r} does not match "
                f"effective tenant {self.effective_tenant_id!r}"
            )
