"""Unit tests for security primitives (JWT + bcrypt), external ADR-0002."""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.access.errors import InvalidTokenError
from libs.access.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    JwtService,
    hash_password,
    verify_password,
)

SECRET = "dev-secret-key"


@pytest.fixture
def jwt():
    return JwtService(
        algorithm="HS256",
        secret_key=SECRET,
        access_expire_minutes=15,
        refresh_expire_days=7,
    )


def test_hash_password_is_not_plaintext_and_verifies():
    hashed = hash_password("cosmonitor")
    assert hashed != "cosmonitor"
    assert hashed.startswith("$2b$")
    assert verify_password("cosmonitor", hashed)
    assert not verify_password("wrong-password", hashed)


def test_hash_password_is_salted_per_call():
    assert hash_password("cosmonitor") != hash_password("cosmonitor")


def test_verify_password_handles_invalid_hash_gracefully():
    assert not verify_password("x", "not-a-bcrypt-hash")


def test_access_token_roundtrip_carries_identity_authority_tenant(jwt):
    token = jwt.create_access_token(
        user_id="u1", tenant_id="t1", email="a@b.c", role="admin"
    )
    payload = jwt.verify_access_token(token)
    assert payload.user_id == "u1"
    assert payload.tenant_id == "t1"
    assert payload.email == "a@b.c"
    assert payload.role == "admin"
    assert payload.is_access
    assert not payload.is_refresh


def test_refresh_token_roundtrip(jwt):
    token = jwt.create_refresh_token(
        user_id="u1", tenant_id="t1", email="a@b.c", role="viewer"
    )
    payload = jwt.verify_refresh_token(token)
    assert payload.role == "viewer"
    assert payload.is_refresh


def test_access_token_rejected_as_refresh_and_vice_versa(jwt):
    access = jwt.create_access_token(
        user_id="u1", tenant_id="t1", email="a@b.c", role="admin"
    )
    refresh = jwt.create_refresh_token(
        user_id="u1", tenant_id="t1", email="a@b.c", role="admin"
    )
    with pytest.raises(InvalidTokenError):
        jwt.verify_refresh_token(access)
    with pytest.raises(InvalidTokenError):
        jwt.verify_access_token(refresh)


def test_expired_token_rejected(jwt):
    expired = JwtService(
        algorithm="HS256",
        secret_key=SECRET,
        access_expire_minutes=-1,  # already expired at issuance
        refresh_expire_days=0,
    )
    token = expired.create_access_token(
        user_id="u1", tenant_id="t1", email="a@b.c", role="viewer"
    )
    with pytest.raises(InvalidTokenError):
        jwt.verify_access_token(token)


def test_tampered_token_rejected(jwt):
    token = jwt.create_access_token(
        user_id="u1", tenant_id="t1", email="a@b.c", role="admin"
    )
    with pytest.raises(InvalidTokenError):
        jwt.verify_access_token(token + "tampered")


def test_wrong_secret_rejected(jwt):
    token = jwt.create_access_token(
        user_id="u1", tenant_id="t1", email="a@b.c", role="admin"
    )
    other = JwtService(algorithm="HS256", secret_key="other-secret")
    with pytest.raises(InvalidTokenError):
        other.verify_access_token(token)


def test_rs256_requires_keys():
    with pytest.raises(ValueError):
        JwtService(algorithm="RS256")


def test_exp_claim_is_absolute_epoch():
    jwt_service = JwtService(
        algorithm="HS256", secret_key=SECRET, access_expire_minutes=15
    )
    token = jwt_service.create_access_token(
        user_id="u1", tenant_id="t1", email="a@b.c", role="viewer"
    )
    payload = jwt_service.verify_access_token(token)
    now = datetime.now(UTC)
    assert payload.exp > int(now.timestamp())
    assert payload.exp <= int((now + timedelta(minutes=16)).timestamp())


def test_token_types_constants():
    assert TOKEN_TYPE_ACCESS == "access"
    assert TOKEN_TYPE_REFRESH == "refresh"