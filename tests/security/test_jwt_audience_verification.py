"""JWT audience verification: the ``verify_aud=False`` switch is config-conditional.

Executable proof for the audit finding "``libs/access/security.py`` disables
audience verification on the machine path": the disabled branch only applies
when no audience is configured, so it is not a permanent bypass.

1. Machine verifier WITH an audience rejects a token carrying a foreign ``aud``.
2. The same token is accepted only while the verifier has no audience
   configured (the conditional branch) — and the shipped configuration
   (.env.example + every entry point) configures ``JWT_AUDIENCE``.
3. The human path has no switch at all: a verifier without an audience still
   rejects a token that carries a foreign ``aud`` (python-jose fail-closed).
4. Machine tokens without ``aud`` (ADR-0005 claim set) keep verifying when an
   audience is configured: the enforcement must not break the real token flow.
5. Report-service wires issuer/audience like the minting side, so gateway
   tokens verify there instead of being rejected with "Invalid audience".
"""
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from libs.access.errors import InvalidTokenError
from libs.access.security import JwtService, MachineJwtService

ROOT = Path(__file__).resolve().parents[2]
SECRET = "audience-proof-secret"
# gateway wires JWT_AUDIENCE into the human JwtService and the configured
# MachineJwtService (the dev fallback has no machine keys to configure).
GATEWAY_AUDIENCE_WIRES = 2


def _rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


# One key pair for the whole module: signer and verifier MUST share the key set
# (otherwise the test would fail on signature/kid instead of on the audience).
_PRIVATE_PEM, _PUBLIC_PEM = _rsa_keypair()
KEY_SET = {"k1": (_PRIVATE_PEM, _PUBLIC_PEM)}


def _machine(audience: str | None) -> MachineJwtService:
    return MachineJwtService(
        key_set=KEY_SET,
        active_kid="k1",
        audience=audience,
    )


def _foreign_audience_token() -> str:
    """Machine-format token carrying an audience minted for someone else."""
    svc = _machine("other-service")
    return svc.create_access_token(
        credential_id="11111111-1111-1111-1111-111111111111",
        tenant_id="22222222-2222-2222-2222-222222222222",
        extra_claims={"aud": "other-service"},
    )


class TestMachineAudienceEnforcedWhenConfigured:
    """Audience verification IS active on the machine path when configured."""

    def test_foreign_audience_rejected(self):
        verifier = _machine(audience="cosmonitor")
        token = _foreign_audience_token()
        with pytest.raises(InvalidTokenError, match="audience"):
            verifier.verify_access_token(token)

    def test_own_machine_token_still_accepted(self):
        """ADR-0005 tokens carry no `aud`: configuring audience must not break them."""
        verifier = _machine(audience="cosmonitor")
        token = verifier.create_access_token(
            credential_id="11111111-1111-1111-1111-111111111111",
            tenant_id="22222222-2222-2222-2222-222222222222",
        )
        payload = verifier.verify_access_token(token)
        assert payload.tenant_id == "22222222-2222-2222-2222-222222222222"

    def test_human_token_is_still_gated_by_token_type(self):
        """Audience is not the only gate: cross-context reuse stays rejected."""
        verifier = _machine(audience="cosmonitor")
        mint = JwtService(algorithm="HS256", secret_key=SECRET, audience="cosmonitor")
        human_token = mint.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        with pytest.raises(InvalidTokenError):
            verifier.decode(human_token)


class TestAudienceSwitchIsConditional:
    """`verify_aud=False` exists only in the unconfigured state, and is not the default."""

    def test_unconfigured_verifier_is_the_only_state_that_accepts_foreign_aud(self):
        unconfigured = _machine(audience=None)
        assert unconfigured.audience is None, (
            "the disabled branch is reachable only when audience is unset"
        )
        token = _foreign_audience_token()
        claims = unconfigured.decode(token)
        assert claims["aud"] == "other-service"

        configured = _machine(audience="cosmonitor")
        with pytest.raises(InvalidTokenError, match="audience"):
            configured.decode(token)

    def test_shipped_config_sets_jwt_audience(self):
        content = (ROOT / ".env.example").read_text()
        values = [
            line.split("=", 1)[1].strip()
            for line in content.splitlines()
            if line.startswith("JWT_AUDIENCE=")
        ]
        assert values, ".env.example must declare JWT_AUDIENCE"
        value = values[0]
        assert value and not value.startswith(("<", "REPLACE", "CHANGE")), (
            "shipped JWT_AUDIENCE must be a real audience, not a placeholder"
        )

    def test_entry_points_wire_jwt_audience_into_verifiers(self):
        """Every minting/verifying entry point reads JWT_AUDIENCE from env."""
        gateway = (ROOT / "apps/gateway/api-gateway/src/main.py").read_text()
        assert gateway.count('audience=os.getenv("JWT_AUDIENCE")') >= (
            GATEWAY_AUDIENCE_WIRES
        ), "gateway must pass JWT_AUDIENCE to the human AND machine services"
        user_service = (
            ROOT / "apps/services/user-service/src/auth/security.py"
        ).read_text()
        assert 'os.getenv("JWT_AUDIENCE")' in user_service
        report_service = (ROOT / "apps/services/report-service/src/main.py").read_text()
        assert 'audience=os.getenv("JWT_AUDIENCE")' in report_service, (
            "report-service must verify the same audience the gateway mints"
        )
        assert 'issuer=os.getenv("JWT_ISSUER")' in report_service


class TestHumanPathHasNoAudienceSwitch:
    """The human verifier never disables audience checks."""

    def test_verifier_without_audience_rejects_foreign_aud(self):
        mint = JwtService(algorithm="HS256", secret_key=SECRET, audience="someone-else")
        token = mint.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        unconfigured = JwtService(algorithm="HS256", secret_key=SECRET)
        with pytest.raises(InvalidTokenError, match="audience"):
            unconfigured.verify_access_token(token)

    def test_parity_between_mint_and_report_verifier(self):
        """Report-service config (issuer+audience) accepts a gateway-style token."""
        mint = JwtService(
            algorithm="HS256",
            secret_key=SECRET,
            issuer="http://localhost",
            audience="cosmonitor",
        )
        verify = JwtService(
            algorithm="HS256",
            secret_key=SECRET,
            issuer="http://localhost",
            audience="cosmonitor",
        )
        token = mint.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        assert verify.verify_access_token(token).user_id == "u1"
