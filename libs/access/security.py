"""Credential hashing + JWT issuance/verification (external, ADR-0002).

Pure-ish security primitives shared by the user-service (emits tokens) and the
API Gateway (verifies tokens). There is NO cognitive capability here (R1 for
the external layer: authenticate/authorize, never reason): this module only
turns credentials into a verifiable identity claim and back.

Bcrypt: ``passlib[bcrypt]`` is declared in ``pyproject.toml`` but passlib 1.7.4
is incompatible with bcrypt >= 4.1 (it reads the removed
``bcrypt.__about__.__version__`` attribute). This environment ships bcrypt
5.0.0, so hashing uses the ``bcrypt`` package DIRECTLY (no new dependency;
``bcrypt`` is already installed via ``passlib[bcrypt]``). Documented in the
Sprint 12 journal.

JWT: python-jose. Development uses HS256 with ``JWT_SECRET_KEY``; production
uses RS256 with ``JWT_PRIVATE_KEY`` (signing) and ``JWT_PUBLIC_KEY`` (verify).
Access tokens expire in minutes, refresh tokens in days; both carry the
Decision Authority claim (role) and the tenant scope so every authorized action
has an auditable authority binding (R5).
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt as bcrypt_lib
from jose import JWTError, jwt

from libs.access.errors import InvalidTokenError

# bcrypt cost factor (OWASP guidance: >= 10; 12 is the 2026 default).
BCRYPT_ROUNDS = 12

# Token kinds issued by the user-service.
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# JWT standard claims.
CLAIM_SUB = "sub"  # user_id
CLAIM_TENANT = "tenant_id"
CLAIM_EMAIL = "email"
CLAIM_ROLE = "role"
CLAIM_TYPE = "token_type"
CLAIM_EXP = "exp"
CLAIM_IAT = "iat"


def hash_password(password: str) -> str:
    """Bcrypt hash of a plaintext password (never stored as plaintext)."""
    hashed = bcrypt_lib.hashpw(
        password.encode("utf-8"), bcrypt_lib.gensalt(rounds=BCRYPT_ROUNDS)
    )
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time-ish comparison of a password against a bcrypt hash."""
    try:
        return bcrypt_lib.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


@dataclass(frozen=True)
class TokenPayload:
    """Verified claims of a JWT: identity + Decision Authority + tenant scope."""

    user_id: str
    tenant_id: str
    email: str
    role: str
    token_type: str
    exp: int

    @property
    def is_refresh(self) -> bool:
        return self.token_type == TOKEN_TYPE_REFRESH

    @property
    def is_access(self) -> bool:
        return self.token_type == TOKEN_TYPE_ACCESS


class JwtService:
    """Issue and verify signed JWTs (HS256 dev / RS256 prod).

    Never trusts claims from the payload alone: every verification re-checks
    the signature, the expiry and the expected token type.
    """

    def __init__(  # noqa: PLR0913 - JWT config bundle (secret, keys, expiries)
        self,
        *,
        algorithm: str = "HS256",
        secret_key: str | None = None,
        private_key: str | None = None,
        public_key: str | None = None,
        access_expire_minutes: int = 15,
        refresh_expire_days: int = 7,
    ):
        self.algorithm = algorithm
        self.secret_key = secret_key
        self.private_key = private_key
        self.public_key = public_key
        self.access_expire_minutes = access_expire_minutes
        self.refresh_expire_days = refresh_expire_days
        if algorithm == "RS256":
            if not private_key or not public_key:
                raise ValueError(  # noqa: TRY003 - config error, one message
                    "JWT_ALGORITHM=RS256 requires JWT_PRIVATE_KEY and "
                    "JWT_PUBLIC_KEY (production signing/verification keys)"
                )
        elif algorithm != "HS256":
            raise ValueError(  # noqa: TRY003 - config error, one message
                f"unsupported JWT algorithm: {algorithm} (use HS256 or RS256)"
            )
        if not secret_key and algorithm == "HS256":
            raise ValueError(  # noqa: TRY003 - config error, one message
                "JWT_ALGORITHM=HS256 requires JWT_SECRET_KEY (dev key)"
            )

    def _sign(self, claims: dict[str, Any]) -> str:
        key = self.private_key if self.algorithm == "RS256" else self.secret_key
        return jwt.encode(claims, key, algorithm=self.algorithm)

    def create_token(  # noqa: PLR0913 - token claims bundle
        self,
        *,
        user_id: str,
        tenant_id: str,
        email: str,
        role: str,
        token_type: str,
        expires_delta: timedelta,
    ) -> str:
        """Sign a token with the identity + authority + tenant claims."""
        now = datetime.now(UTC)
        claims = {
            CLAIM_SUB: str(user_id),
            CLAIM_TENANT: str(tenant_id),
            CLAIM_EMAIL: email,
            CLAIM_ROLE: role,
            CLAIM_TYPE: token_type,
            CLAIM_IAT: int(now.timestamp()),
            CLAIM_EXP: int((now + expires_delta).timestamp()),
        }
        return self._sign(claims)

    def create_access_token(
        self,
        *,
        user_id: str,
        tenant_id: str,
        email: str,
        role: str,
    ) -> str:
        return self.create_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role,
            token_type=TOKEN_TYPE_ACCESS,
            expires_delta=timedelta(minutes=self.access_expire_minutes),
        )

    def create_refresh_token(
        self,
        *,
        user_id: str,
        tenant_id: str,
        email: str,
        role: str,
    ) -> str:
        return self.create_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role,
            token_type=TOKEN_TYPE_REFRESH,
            expires_delta=timedelta(days=self.refresh_expire_days),
        )

    def decode(self, token: str) -> dict[str, Any]:
        """Verify signature + expiry and return the raw claims.

        Raises InvalidTokenError on malformed/expired/tampered tokens (-> 401).
        """
        key = self.public_key if self.algorithm == "RS256" else self.secret_key
        try:
            return jwt.decode(
                token,
                key,
                algorithms=[self.algorithm],
                options={"verify_aud": False},
            )
        except JWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

    def decode_payload(self, token: str, *, expected_type: str) -> TokenPayload:
        """Verified TokenPayload restricted to the expected token kind."""
        claims = self.decode(token)
        if claims.get(CLAIM_TYPE) != expected_type:
            raise InvalidTokenError(  # noqa: TRY003 - declarative, one message
                f"token is not a {expected_type} token (got {claims.get(CLAIM_TYPE)})"
            )
        try:
            return TokenPayload(
                user_id=str(claims[CLAIM_SUB]),
                tenant_id=str(claims[CLAIM_TENANT]),
                email=str(claims[CLAIM_EMAIL]),
                role=str(claims[CLAIM_ROLE]),
                token_type=str(claims[CLAIM_TYPE]),
                exp=int(claims[CLAIM_EXP]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError(  # noqa: TRY003 - declarative, one message
                "token payload is missing required claims"
            ) from exc

    def verify_access_token(self, token: str) -> TokenPayload:
        return self.decode_payload(token, expected_type=TOKEN_TYPE_ACCESS)

    def verify_refresh_token(self, token: str) -> TokenPayload:
        return self.decode_payload(token, expected_type=TOKEN_TYPE_REFRESH)