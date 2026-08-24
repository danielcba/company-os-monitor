"""Access errors - external capability (ADR-0002).

Typed errors shared by the user-service and the API Gateway so both map the
same failure to the right HTTP status: invalid/missing credentials are 401
(authentication), an authenticated caller without the required role/scope is
403 (authorization). The distinction is the enforcement contract of the
Cognitive Boundary (R3): Perception/Reasoning never execute action without
explicit authorization.
"""


class AccessError(Exception):
    """Base class for access-layer failures (external, ADR-0002)."""


class InvalidTokenError(AccessError):
    """Missing, malformed, expired or unverifiable token (-> 401)."""

    @classmethod
    def missing_bearer(cls) -> "InvalidTokenError":
        return cls("missing bearer token")

    @classmethod
    def revoked(cls) -> "InvalidTokenError":
        return cls("token has been revoked")

    @classmethod
    def security_unavailable(cls) -> "InvalidTokenError":
        return cls("security control unavailable; token cannot be verified")


class AuthenticationError(AccessError):
    """Credentials do not authenticate a valid identity (-> 401)."""


class AuthorizationError(AccessError):
    """Authenticated identity lacks the authority for the action (-> 403)."""


class TenantIsolationError(AuthorizationError):
    """Cross-tenant access attempted without cross-tenant authority (-> 403)."""


class UserConflictError(AccessError):
    """A user with the same unique identity already exists (-> 409)."""


class InvalidRoleError(AccessError):
    """Requested role is not a declared Decision Authority role (-> 400)."""