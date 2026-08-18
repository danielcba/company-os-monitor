"""Security facade - env-driven JWT + credential primitives (external).

Re-exports the shared primitives from ``libs.access.security`` (single source
of truth for the user-service AND the API Gateway) and builds the runtime
``JwtService`` from the environment. Development uses HS256 with
``JWT_SECRET_KEY``; production uses RS256 with ``JWT_PRIVATE_KEY``/
``JWT_PUBLIC_KEY``. No cognitive capability here (ADR-0002): this only turns
credentials into a verifiable identity+authority claim.
"""
import os

from libs.access.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    JwtService,
    TokenPayload,
    hash_password,
    verify_password,
)

__all__ = [
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
    "JwtService",
    "TokenPayload",
    "build_jwt_service_from_env",
    "hash_password",
    "verify_password",
]


def build_jwt_service_from_env() -> JwtService:
    """JwtService configured from JWT_* env vars (HS256 dev / RS256 prod)."""
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    secret_key = os.getenv("JWT_SECRET_KEY")
    private_key = os.getenv("JWT_PRIVATE_KEY")
    public_key = os.getenv("JWT_PUBLIC_KEY")
    return JwtService(
        algorithm=algorithm,
        secret_key=secret_key,
        private_key=private_key,
        public_key=public_key,
        access_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")),
        refresh_expire_days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
    )