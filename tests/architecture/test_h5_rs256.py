"""H5 — RS256 Machine JWT Authentication Tests.

Verifies: MachineJwtService key separation, kid-based rotation, RS256 signing,
fail-closed validation, and complete separation from human JwtService.

Maps to ADR-0005 §1 (Key Rotation) and H5 acceptance criteria.
"""

from __future__ import annotations

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jose import jwt

from libs.access.errors import InvalidTokenError
from libs.access.security import (
    MACHINE_TOKEN_TYPE_ACCESS,
    MACHINE_TOKEN_TYPE_REFRESH,
    MACHINE_TOKEN_TYPE_REGISTRATION,
    JwtService,
    MachineJwtService,
)


def _generate_key_pair() -> tuple[str, str]:
    """Generate an RSA key pair and return (private_pem, public_pem)."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv_pem, pub_pem


KEY_A_PRIV, KEY_A_PUB = _generate_key_pair()
KEY_B_PRIV, KEY_B_PUB = _generate_key_pair()
KEY_C_PRIV, KEY_C_PUB = _generate_key_pair()  # unknown key for testing


@pytest.fixture
def machine_jwt_a() -> MachineJwtService:
    """MachineJwtService with kid=A as active."""
    return MachineJwtService(
        key_set={"A": (KEY_A_PRIV, KEY_A_PUB)},
        active_kid="A",
    )


@pytest.fixture
def machine_jwt_ab() -> MachineJwtService:
    """MachineJwtService with kid=B active, kid=A available for overlap."""
    return MachineJwtService(
        key_set={
            "A": (KEY_A_PRIV, KEY_A_PUB),
            "B": (KEY_B_PRIV, KEY_B_PUB),
        },
        active_kid="B",
    )


@pytest.fixture
def human_jwt() -> JwtService:
    """Human JwtService (HS256) — completely separate."""
    return JwtService(algorithm="HS256", secret_key="human-secret-key")


# ---------------------------------------------------------------------------
# 1. Machine JWT valid issuance
# ---------------------------------------------------------------------------

class TestMachineJwtIssuance:
    def test_valid_access_token(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_valid_refresh_token(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_refresh_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        assert isinstance(token, str)

    def test_valid_registration_token(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_registration_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
            installation_id="inst-001",
        )
        assert isinstance(token, str)


# ---------------------------------------------------------------------------
# 2. Header contains kid
# ---------------------------------------------------------------------------

class TestKidInHeader:
    def test_kid_in_header(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        header = jwt.get_unverified_header(token)
        assert header.get("kid") == "A"

    def test_alg_rs256_in_header(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        header = jwt.get_unverified_header(token)
        assert header.get("alg") == "RS256"


# ---------------------------------------------------------------------------
# 3. Algorithm = RS256
# ---------------------------------------------------------------------------

class TestRs256Algorithm:
    def test_token_signed_with_rs256(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "RS256"

    def test_hs256_token_rejected_by_machine_service(self, machine_jwt_a: MachineJwtService):
        """A token signed with HS256 (human) must not be accepted by MachineJwtService."""
        # Create an HS256 token using a human JwtService-like approach
        hs256_token = jwt.encode(
            {"sub": "test", "token_type": "machine_access", "exp": 9999999999},
            "secret",
            algorithm="HS256",
        )
        with pytest.raises(InvalidTokenError):
            machine_jwt_a.decode(hs256_token)


# ---------------------------------------------------------------------------
# 4. Claims machine correctos
# ---------------------------------------------------------------------------

class TestMachineClaims:
    def test_access_token_claims(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
            extra_claims={"installation_id": "inst-001", "scopes": ["telemetry:ingest"]},
        )
        payload = machine_jwt_a.verify_access_token(token)
        assert payload.user_id == "cred-001"
        assert payload.tenant_id == "tenant-001"
        assert payload.installation_id == "inst-001"
        assert payload.token_type == MACHINE_TOKEN_TYPE_ACCESS

    def test_refresh_token_claims(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_refresh_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        payload = machine_jwt_a.verify_refresh_token(token)
        assert payload.token_type == MACHINE_TOKEN_TYPE_REFRESH

    def test_registration_token_claims(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_registration_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
            installation_id="inst-001",
        )
        payload = machine_jwt_a.verify_registration_token(token)
        assert payload.token_type == MACHINE_TOKEN_TYPE_REGISTRATION
        assert payload.installation_id == "inst-001"


# ---------------------------------------------------------------------------
# 5. ACTIVE_KID controls issuance
# ---------------------------------------------------------------------------

class TestActiveKidControlsIssuance:
    def test_uses_active_kid(self, machine_jwt_ab: MachineJwtService):
        """When active_kid=B, new tokens must have kid=B."""
        token = machine_jwt_ab.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        header = jwt.get_unverified_header(token)
        assert header.get("kid") == "B"

    def test_active_kid_property(self, machine_jwt_a: MachineJwtService):
        assert machine_jwt_a.active_kid == "A"

    def test_active_kid_must_exist_in_key_set(self):
        with pytest.raises(ValueError, match="not found in key_set"):
            MachineJwtService(
                key_set={"A": (KEY_A_PRIV, KEY_A_PUB)},
                active_kid="NONEXISTENT",
            )


# ---------------------------------------------------------------------------
# 6. Validation uses kid from token
# ---------------------------------------------------------------------------

class TestValidationUsesKid:
    def test_valid_token_with_correct_kid(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        payload = machine_jwt_a.verify_access_token(token)
        assert payload.user_id == "cred-001"

    def test_decode_extracts_kid(self, machine_jwt_a: MachineJwtService):
        token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        # Decode raw claims (without signature verification for header inspection)
        raw_header = jwt.get_unverified_header(token)
        assert raw_header["kid"] == "A"


# ---------------------------------------------------------------------------
# 7. Key A cannot validate token signed by key B
# ---------------------------------------------------------------------------

class TestCrossKeyRejection:
    def test_key_a_rejects_token_signed_by_key_b(self):
        """Token signed with kid=B must be rejected by service with only kid=A."""
        svc_a = MachineJwtService(
            key_set={"A": (KEY_A_PRIV, KEY_A_PUB)},
            active_kid="A",
        )
        svc_b = MachineJwtService(
            key_set={"B": (KEY_B_PRIV, KEY_B_PUB)},
            active_kid="B",
        )
        token_b = svc_b.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        with pytest.raises(InvalidTokenError):
            svc_a.decode(token_b)

    def test_key_b_rejects_token_signed_by_key_a(self):
        """Token signed with kid=A must be rejected by service with only kid=B."""
        svc_a = MachineJwtService(
            key_set={"A": (KEY_A_PRIV, KEY_A_PUB)},
            active_kid="A",
        )
        svc_b = MachineJwtService(
            key_set={"B": (KEY_B_PRIV, KEY_B_PUB)},
            active_kid="B",
        )
        token_a = svc_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        with pytest.raises(InvalidTokenError):
            svc_b.decode(token_a)


# ---------------------------------------------------------------------------
# 8. Mismatch between kid and actual signing key
# ---------------------------------------------------------------------------

class TestKidMismatch:
    def test_tampered_kid_rejected(self, machine_jwt_a: MachineJwtService):
        """A token with kid=A in header but signed with key B must fail."""
        # Sign with key B but manually set kid=A in header
        claims = {
            "sub": "cred-001",
            "tenant_id": "tenant-001",
            "token_type": "machine_access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "jti": "test-jti",
        }
        # Sign with key B
        token_with_b = jwt.encode(
            claims, KEY_B_PRIV, algorithm="RS256", headers={"kid": "A"}
        )
        # Service has kid=A mapped to key A — verification should fail
        with pytest.raises(InvalidTokenError):
            machine_jwt_a.decode(token_with_b)


# ---------------------------------------------------------------------------
# 9. Unknown kid rejected
# ---------------------------------------------------------------------------

class TestUnknownKid:
    def test_unknown_kid_rejected(self, machine_jwt_a: MachineJwtService):
        """Token with kid=C (not in key_set) must be rejected."""
        claims = {
            "sub": "cred-001",
            "tenant_id": "tenant-001",
            "token_type": "machine_access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "jti": "test-jti",
        }
        token_c = jwt.encode(
            claims, KEY_C_PRIV, algorithm="RS256", headers={"kid": "C"}
        )
        with pytest.raises(InvalidTokenError, match="unknown kid"):
            machine_jwt_a.decode(token_c)


# ---------------------------------------------------------------------------
# 10. Missing kid rejected
# ---------------------------------------------------------------------------

class TestMissingKid:
    def test_missing_kid_rejected(self, machine_jwt_a: MachineJwtService):
        """Token without kid header must be rejected."""
        claims = {
            "sub": "cred-001",
            "tenant_id": "tenant-001",
            "token_type": "machine_access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "jti": "test-jti",
        }
        token_no_kid = jwt.encode(
            claims, KEY_A_PRIV, algorithm="RS256", headers={"typ": "JWT"}
        )
        with pytest.raises(InvalidTokenError, match="missing required kid"):
            machine_jwt_a.decode(token_no_kid)


# ---------------------------------------------------------------------------
# 11. Rotation: old key valid during overlap
# ---------------------------------------------------------------------------

class TestRotationOverlap:
    def test_old_key_valid_during_overlap(self):
        """Token signed with kid=A remains valid when active_kid=B (overlap)."""
        svc = MachineJwtService(
            key_set={
                "A": (KEY_A_PRIV, KEY_A_PUB),
                "B": (KEY_B_PRIV, KEY_B_PUB),
            },
            active_kid="B",
        )
        # Sign with key A (old key, still in key_set)
        token_a = jwt.encode(
            {
                "sub": "cred-001",
                "tenant_id": "tenant-001",
                "token_type": "machine_access",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
                "jti": "old-jti",
            },
            KEY_A_PRIV,
            algorithm="RS256",
            headers={"kid": "A"},
        )
        # Should still validate (A is in key_set)
        payload = svc.decode(token_a)
        assert payload["sub"] == "cred-001"

    def test_new_tokens_use_new_active_kid(self):
        """After rotation, new tokens must use the new active_kid."""
        svc = MachineJwtService(
            key_set={
                "A": (KEY_A_PRIV, KEY_A_PUB),
                "B": (KEY_B_PRIV, KEY_B_PUB),
            },
            active_kid="B",
        )
        token = svc.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        header = jwt.get_unverified_header(token)
        assert header["kid"] == "B"


# ---------------------------------------------------------------------------
# 12. Retired key rejected after removal from key_set
# ---------------------------------------------------------------------------

class TestRetiredKeyRejection:
    def test_retired_key_rejected(self):
        """Token signed with kid=A must be rejected when A is removed from key_set."""
        svc_after_retirement = MachineJwtService(
            key_set={"B": (KEY_B_PRIV, KEY_B_PUB)},
            active_kid="B",
        )
        token_a = jwt.encode(
            {
                "sub": "cred-001",
                "tenant_id": "tenant-001",
                "token_type": "machine_access",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
                "jti": "retired-jti",
            },
            KEY_A_PRIV,
            algorithm="RS256",
            headers={"kid": "A"},
        )
        with pytest.raises(InvalidTokenError, match="unknown kid"):
            svc_after_retirement.decode(token_a)


# ---------------------------------------------------------------------------
# 13. Human JWT cannot be validated as machine
# ---------------------------------------------------------------------------

class TestHumanMachineSeparation:
    def test_human_jwt_rejected_by_machine_service(
        self, human_jwt: JwtService, machine_jwt_a: MachineJwtService
    ):
        """A human JWT signed with HS256 must be rejected by MachineJwtService."""
        human_token = human_jwt.create_access_token(
            user_id="user-001",
            tenant_id="tenant-001",
            email="user@example.com",
            role="admin",
        )
        with pytest.raises(InvalidTokenError):
            machine_jwt_a.decode(human_token)

    def test_machine_jwt_cannot_be_used_by_human_flow(
        self, machine_jwt_a: MachineJwtService, human_jwt: JwtService
    ):
        """A machine RS256 token must be rejected by human JwtService (HS256)."""
        machine_token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        with pytest.raises(InvalidTokenError):
            human_jwt.decode(machine_token)

    def test_machine_token_type_not_accepted_by_human_verify(
        self, machine_jwt_a: MachineJwtService, human_jwt: JwtService
    ):
        """Machine token_type 'machine_access' must not pass human verify_access_token."""
        machine_token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        with pytest.raises(InvalidTokenError):
            human_jwt.verify_access_token(machine_token)


# ---------------------------------------------------------------------------
# 14. Configuration failure modes
# ---------------------------------------------------------------------------

class TestConfigurationFailures:
    def test_empty_key_set_rejected(self):
        with pytest.raises(ValueError, match="at least one key"):
            MachineJwtService(key_set={}, active_kid="A")

    def test_active_kid_not_in_key_set_rejected(self):
        with pytest.raises(ValueError, match="not found in key_set"):
            MachineJwtService(
                key_set={"A": (KEY_A_PRIV, KEY_A_PUB)},
                active_kid="B",
            )

    def test_no_fallback_to_human_keys(
        self, human_jwt: JwtService, machine_jwt_a: MachineJwtService
    ):
        """MachineJwtService must never use human keys as fallback."""
        # Create a human token
        human_token = human_jwt.create_access_token(
            user_id="user-001",
            tenant_id="tenant-001",
            email="user@example.com",
            role="admin",
        )
        # Machine service must reject it, not fall back to human keys
        with pytest.raises(InvalidTokenError):
            machine_jwt_a.decode(human_token)


# ---------------------------------------------------------------------------
# 15. Non-RS256 algorithms rejected
# ---------------------------------------------------------------------------

class TestNonRs256Rejection:
    def test_hs256_token_rejected(self, machine_jwt_a: MachineJwtService):
        """HS256 token must be rejected by RS256-only MachineJwtService."""
        hs256_token = jwt.encode(
            {"sub": "test", "token_type": "machine_access", "exp": 9999999999},
            "secret",
            algorithm="HS256",
        )
        with pytest.raises(InvalidTokenError):
            machine_jwt_a.decode(hs256_token)

    def test_es256_token_rejected(self, machine_jwt_a: MachineJwtService):
        """ES256 token must be rejected by RS256-only MachineJwtService."""
        ec_priv = ec.generate_private_key(ec.SECP256R1())
        ec_token = jwt.encode(
            {"sub": "test", "token_type": "machine_access", "exp": 9999999999},
            ec_priv,
            algorithm="ES256",
        )
        with pytest.raises(InvalidTokenError):
            machine_jwt_a.decode(ec_token)


# ---------------------------------------------------------------------------
# 16. Expired token rejected
# ---------------------------------------------------------------------------

class TestExpiredToken:
    def test_expired_token_rejected(self, machine_jwt_a: MachineJwtService):
        """Expired token must be rejected."""
        token = jwt.encode(
            {
                "sub": "cred-001",
                "tenant_id": "tenant-001",
                "token_type": "machine_access",
                "iat": int(time.time()) - 7200,
                "exp": int(time.time()) - 3600,
                "jti": "expired-jti",
            },
            KEY_A_PRIV,
            algorithm="RS256",
            headers={"kid": "A"},
        )
        with pytest.raises(InvalidTokenError):
            machine_jwt_a.decode(token)


# ---------------------------------------------------------------------------
# 17. Token type mismatch rejected
# ---------------------------------------------------------------------------

class TestTokenTypeMismatch:
    def test_access_token_rejected_as_refresh(self, machine_jwt_a: MachineJwtService):
        """Access token must not pass verify_refresh_token."""
        token = machine_jwt_a.create_access_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        with pytest.raises(InvalidTokenError, match="is not a machine_refresh"):
            machine_jwt_a.verify_refresh_token(token)

    def test_refresh_token_rejected_as_registration(self, machine_jwt_a: MachineJwtService):
        """Refresh token must not pass verify_registration_token."""
        token = machine_jwt_a.create_refresh_token(
            credential_id="cred-001",
            tenant_id="tenant-001",
        )
        with pytest.raises(InvalidTokenError, match="is not a registration_token"):
            machine_jwt_a.verify_registration_token(token)


# ---------------------------------------------------------------------------
# 18. Key set is a copy (no mutation)
# ---------------------------------------------------------------------------

class TestKeySetImmutability:
    def test_key_set_returns_copy(self, machine_jwt_a: MachineJwtService):
        ks = machine_jwt_a.key_set
        ks["X"] = ("priv", "pub")
        assert "X" not in machine_jwt_a.key_set
