"""AuthService - identity verification, token issuance, authorization (external).

External non-canonical capability (ADR-0002). This service is the Decision
Authority issuer for COS-Monitor:

- ``login`` verifies credentials (bcrypt) against a tenant-scoped user and
  issues an access + refresh token pair. Every token carries the identity, the
  tenant scope and the Decision Authority role (core-concepts/decision.md: the
  commitment authority under which a Decision is taken).
- ``refresh`` rotates the refresh token: blacklists the old one and issues a
  new access+refresh pair (stateless JWT strategy with Redis-backed revocation).
- ``logout`` blacklists the refresh token to revoke access immediately.
- ``create_user``/``list_users`` enforce multi-tenant isolation: a role only
  sees its own tenant unless it holds cross-tenant authority (superadmin).
- ``authorize`` decides whether a role may execute an action (RBAC -> Decision
  Authority binding, docs/04).

It NEVER produces cognitive judgments and NEVER runs the pipeline (R1 external
contract: authenticate/authorize only; R3: it protects the boundary without
becoming the flow).
"""
import logging
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

from libs.access.errors import (
    AccessError,
    AuthenticationError,
    AuthorizationError,
    UserConflictError,
)
from libs.access.rbac import (
    ROLE_SUPERADMIN,
    can,
    commit_allowed,
    cross_tenant_allowed,
    tenant_scope,
)
from libs.access.security import (
    JwtService,
    TokenPayload,
    hash_password,
    verify_password,
)
from libs.access.token_blacklist import TokenBlacklist
from libs.access.users import Tenant, User, UserStore

from src.auth.rbac import validate_role


class AuthService:
    """Orchestrates identity verification, tokens and authority checks."""

    def __init__(
        self,
        user_store: UserStore,
        jwt: JwtService,
        blacklist: TokenBlacklist | None = None,
    ):
        self.user_store = user_store
        self.jwt = jwt
        self.blacklist = blacklist
        self.total_logins = 0
        self.total_login_failures = 0
        self.total_tokens_issued = 0
        self.total_tokens_revoked = 0
        self.total_errors = 0
        self.total_users_created = 0
        self.users_by_role: Counter[str] = Counter()
        self.last_login_at: datetime | None = None

    async def login(
        self,
        *,
        email: str,
        password: str,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """Verify credentials and issue the access+refresh token pair.

        Raises AuthenticationError on unknown user, wrong password, inactive
        user or a tenant assertion mismatch (-> 401).
        """
        user = await self.user_store.get_by_email(email=email)
        if user is None or not verify_password(password, user.password_hash):
            self.total_login_failures += 1
            raise AuthenticationError("invalid credentials")
        if not user.is_active:
            self.total_login_failures += 1
            raise AuthenticationError("user is deactivated")
        if tenant_id is not None and str(user.tenant_id) != str(tenant_id):
            self.total_login_failures += 1
            raise AuthenticationError(
                "tenant assertion does not match the user's tenant"
            )

        self.total_logins += 1
        self.last_login_at = datetime.now(UTC)
        self.users_by_role[user.role] += 1
        return self._issue_token_pair(user)

    async def refresh(self, *, refresh_token: str) -> dict[str, Any]:
        """Rotate the refresh token: atomic consume + issue new access+refresh pair.

        The refresh token is verified by signature + type + expiry; the
        referenced user must still exist and be active. The old refresh token
        is consumed atomically via SET NX EX to prevent replay (consume-once).

        Fail-closed: if Redis is unavailable during consume, the request is
        rejected (SecurityControlUnavailable).
        """
        payload = self.jwt.verify_refresh_token(refresh_token)
        user = await self.user_store.get_by_id(id=uuid.UUID(payload.user_id))
        if user is None or not user.is_active:
            self.total_errors += 1
            raise AuthenticationError("refresh token references an unknown user")
        if self.blacklist and payload.jti:
            consumed = await self.blacklist.consume_refresh_token(
                jti=payload.jti, expires_at=payload.exp
            )
            if not consumed:
                self.total_errors += 1
                raise AuthenticationError(
                    "refresh token has already been used (replay detected)"
                )
        access_token = self._access_token(user)
        new_refresh_token = self.jwt.create_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            role=user.role,
        )
        self.total_tokens_issued += 2
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": self.jwt.access_expire_minutes * 60,
        }

    async def logout(self, *, refresh_token: str) -> None:
        """Blacklist the refresh token to revoke access immediately.

        The access token (15 min TTL) will expire naturally; the refresh
        token is blacklisted to prevent further token renewal.

        Idempotent for invalid tokens (already expired/malformed), but
        propagates infrastructure failures (Redis down) so the caller
        can distinguish "token was invalid" from "revocation failed".
        """
        from libs.access.token_blacklist import SecurityControlUnavailable

        try:
            from libs.access.errors import InvalidTokenError
            payload = self.jwt.verify_refresh_token(refresh_token)
        except InvalidTokenError:
            return  # Token already invalid — idempotent, nothing to revoke.
        if self.blacklist and payload.jti:
            try:
                await self.blacklist.revoke(jti=payload.jti, expires_at=payload.exp)
                self.total_tokens_revoked += 1
            except SecurityControlUnavailable:
                raise  # Infrastructure failure — must not pretend success.
            except Exception:
                logger.exception(
                    "unexpected failure revoking token jti=%s", payload.jti
                )
                self.total_errors += 1

    async def create_user(
        self,
        *,
        actor: TokenPayload,
        email: str,
        password: str,
        name: str | None,
        role: str,
        tenant_id: str | None = None,
    ) -> User:
        """Create a user in a tenant scope (admin/superadmin only).

        An admin creates within its own tenant; only superadmin may request a
        different tenant (cross-tenant authority). Raises AuthorizationError on
        insufficient role, UserConflictError on a duplicate email.
        """
        validate_role(role)
        if not _can_create(actor.role):
            self.total_errors += 1
            raise AuthorizationError(
                f"role {actor.role!r} may not create users (admin/superadmin only)"
            )
        target = tenant_scope(actor.role, actor.tenant_id, tenant_id)
        user = await self.user_store.create_user(
            tenant_id=uuid.UUID(target),
            email=email,
            password_hash=hash_password(password),
            name=name,
            role=role,
            is_active=True,
        )
        if user is None:
            self.total_errors += 1
            raise UserConflictError(f"a user with email {email!r} already exists")
        self.total_users_created += 1
        self.users_by_role[user.role] += 1
        return user

    async def list_users(
        self,
        *,
        actor: TokenPayload,
        tenant_id: str | None = None,
    ) -> list[User]:
        """List users of a tenant scope (admin/superadmin only, isolated).

        Identity data (``users``) is an external capability (ADR-0002); unlike
        the pipeline READ (viewer reads decisions/reports), listing identities
        requires admin/superadmin. A role only sees its own tenant unless it
        holds cross-tenant authority (superadmin).
        """
        if not _can_create(actor.role):
            self.total_errors += 1
            raise AuthorizationError(
                f"role {actor.role!r} may not list users (admin/superadmin only)"
            )
        target = tenant_scope(actor.role, actor.tenant_id, tenant_id)
        return await self.user_store.list_by_tenant(tenant_id=uuid.UUID(target))

    async def list_tenants(self, *, actor: TokenPayload) -> list[Tenant]:
        """List all tenants (superadmin only)."""
        if actor.role != ROLE_SUPERADMIN:
            self.total_errors += 1
            raise AuthorizationError(
                f"role {actor.role!r} may not list tenants (superadmin only)"
            )
        return await self.user_store.list_tenants()

    async def get_tenant(
        self, *, actor: TokenPayload, tenant_id: str
    ) -> Tenant | None:
        """Get a tenant by ID (superadmin only)."""
        if actor.role != ROLE_SUPERADMIN:
            self.total_errors += 1
            raise AuthorizationError(
                f"role {actor.role!r} may not read tenants (superadmin only)"
            )
        return await self.user_store.get_tenant_by_id(id=uuid.UUID(tenant_id))

    async def update_user(
        self,
        *,
        actor: TokenPayload,
        user_id: str,
        name: str | None = None,
        role: str | None = None,
    ) -> User:
        """Update a user (admin/superadmin only, same tenant)."""
        if not _can_create(actor.role):
            self.total_errors += 1
            raise AuthorizationError(
                f"role {actor.role!r} may not update users (admin/superadmin only)"
            )
        target_user = await self.user_store.get_by_id(id=uuid.UUID(user_id))
        if target_user is None:
            raise AccessError("user not found")
        if str(target_user.tenant_id) != actor.tenant_id and actor.role != ROLE_SUPERADMIN:
            self.total_errors += 1
            raise AuthorizationError("cannot update users in another tenant")
        if role is not None:
            validate_role(role)
        updated = await self.user_store.update_user(
            id=uuid.UUID(user_id), name=name, role=role
        )
        if updated is None:
            raise AccessError("user not found")
        return updated

    async def deactivate_user(
        self, *, actor: TokenPayload, user_id: str
    ) -> User:
        """Soft-deactivate a user (admin/superadmin only, same tenant)."""
        if not _can_create(actor.role):
            self.total_errors += 1
            raise AuthorizationError(
                f"role {actor.role!r} may not deactivate users (admin/superadmin only)"
            )
        target_user = await self.user_store.get_by_id(id=uuid.UUID(user_id))
        if target_user is None:
            raise AccessError("user not found")
        if str(target_user.tenant_id) != actor.tenant_id and actor.role != ROLE_SUPERADMIN:
            self.total_errors += 1
            raise AuthorizationError("cannot deactivate users in another tenant")
        deactivated = await self.user_store.deactivate_user(id=uuid.UUID(user_id))
        if deactivated is None:
            raise AccessError("user not found")
        return deactivated

    def authorize(
        self,
        *,
        role: str,
        permission: str,
        risk: str | None = None,
        tenant_id: str | None = None,
        actor_tenant_id: str | None = None,
    ) -> bool:
        """Decision Authority check: may this role execute the action?

        Pure RBAC -> authority binding (docs/04). ``commit`` is further
        constrained by risk tolerance (admin low/medium, superadmin high);
        cross-tenant requests require superadmin.
        """
        if permission in {"read", "ack", "propose", "execute", "define_policy"}:
            if not can(role, permission):
                return False
        elif permission == "commit":
            if not commit_allowed(role, risk):
                return False
        else:
            raise ValueError(f"unknown action permission: {permission!r}")
        if tenant_id and actor_tenant_id and str(tenant_id) != str(actor_tenant_id):
            return cross_tenant_allowed(role)
        return True

    def _issue_token_pair(self, user: User) -> dict[str, Any]:
        access_token = self._access_token(user)
        refresh_token = self.jwt.create_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            role=user.role,
        )
        self.total_tokens_issued += 2
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.jwt.access_expire_minutes * 60,
            "user": {
                "id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
            },
        }

    def _access_token(self, user: User) -> str:
        return self.jwt.create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            role=user.role,
        )

    def metrics(self) -> dict[str, Any]:
        """Operational metrics (no rule numbers) for /metrics."""
        return {
            "total_logins": self.total_logins,
            "total_login_failures": self.total_login_failures,
            "total_tokens_issued": self.total_tokens_issued,
            "total_tokens_revoked": self.total_tokens_revoked,
            "total_errors": self.total_errors,
            "total_users_created": self.total_users_created,
            "users_by_role": dict(self.users_by_role),
            "last_login_at": (
                self.last_login_at.isoformat() if self.last_login_at else None
            ),
        }


def _can_create(role: str) -> bool:
    """Admin and superadmin may create users; viewer/operator cannot."""
    return role in {"admin", ROLE_SUPERADMIN}