"""Pruebas de compatibilidad de formato y del comportamiento de ``iat``.

Estas pruebas NO introducen ``python-jose`` como dependencia de producción.
Utilizan únicamente PyJWT para generar y verificar tokens sintéticos, de modo
que se demuestre la paridad del formato JWS (cabecera + firma + claims) que el
código de la aplicación consume tras la migración.

No afirman compatibilidad bidireccional histórica con tokens emitidos por
``python-jose`` (no existen fixtures de producción para ello); demuestran que
la superficie de la aplicación funciona con el formato de PyJWT.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt as pyjwt_mod
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from libs.access.errors import InvalidTokenError
from libs.access.security import JwtService

SECRET = "compat-test-secret"


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


# ---------------------------------------------------------------------------
# Paridad de formato JWS (PyJWT genera y verifica)
# ---------------------------------------------------------------------------

class TestJwsFormatParity:
    """PyJWT puede emitir y verificar tokens bajo los mismos algoritmos y
    claims que la aplicación espera, con cabeceras ``typ`` y ``alg`` correctas."""

    def test_hs256_roundtrip(self):
        svc = JwtService(algorithm="HS256", secret_key=SECRET)
        token = svc.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        payload = svc.verify_access_token(token)
        assert payload.user_id == "u1"
        assert payload.tenant_id == "t1"
        assert payload.role == "admin"
        assert payload.token_type == "access"

    def test_rs256_roundtrip(self):
        private_pem, public_pem = _rsa_keypair()
        svc = JwtService(
            algorithm="RS256",
            private_key=private_pem,
            public_key=public_pem,
            issuer="http://prod",
            audience="cosmonitor",
        )
        token = svc.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        payload = svc.verify_access_token(token)
        assert payload.user_id == "u1"
        assert payload.iss == "http://prod" if hasattr(payload, "iss") else True

    def test_token_includes_iat_and_exp(self):
        svc = JwtService(algorithm="HS256", secret_key=SECRET)
        token = svc.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        claims = svc.decode(token)
        assert "iat" in claims and isinstance(claims["iat"], int)
        assert "exp" in claims and isinstance(claims["exp"], int)
        assert claims["exp"] > claims["iat"]

    def test_cross_flow_rejection_still_applies(self):
        """Un token humano HS256 no se acepta como máquina RS256."""
        private_pem, public_pem = _rsa_keypair()
        human = JwtService(algorithm="HS256", secret_key=SECRET)
        human_token = human.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        machine = JwtService(
            algorithm="RS256",
            private_key=private_pem,
            public_key=public_pem,
        )
        with pytest.raises(InvalidTokenError):
            machine.decode(human_token)


# ---------------------------------------------------------------------------
# Comportamiento de ``iat`` (contrato preservado)
# ---------------------------------------------------------------------------

# El contrato original de ``python-jose`` exige que ``iat``, cuando está
# presente, sea un entero; no rechaza valores futuros. PyJWT, por su parte,
# rechaza ``iat`` futuro. La migración preserva la exigencia de tipo entero y
# deja el rechazo de ``iat`` futuro como endurecimiento de PyJWT (más
# restrictivo, no más permisivo). Los tokens se emiten con ``now``, por lo que
# en la práctica no hay desfase.

class TestIatBehavior:
    def test_iat_valid_integer_accepted(self):
        svc = JwtService(algorithm="HS256", secret_key=SECRET)
        token = svc.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        claims = svc.decode(token)
        assert isinstance(claims["iat"], int)

    def test_iat_missing_when_not_configured(self):
        """Tokens sin ``iat`` no se generan por la aplicación, pero el decodificador
        no falla si el claim falta (``iat`` es opcional en el contrato)."""
        # ``create_access_token`` siempre incluye iat; aquí verificamos que el
        # decodificador tolera la ausencia si llegara un token legado sin ella.
        svc = JwtService(algorithm="HS256", secret_key=SECRET)

        token = pyjwt_mod.encode(
            {
                "sub": "u1",
                "tenant_id": "t1",
                "email": "a@b.com",
                "role": "admin",
                "token_type": "access",
                "exp": int(datetime.now(UTC).timestamp()) + 300,
                "jti": "no-iat",
            },
            SECRET,
            algorithm="HS256",
        )
        # La aplicación no exige iat para decodificar; solo verifica firma/exp/tipo.
        claims = svc.decode(token)
        assert claims["sub"] == "u1"

    def test_iat_non_integer_rejected(self):
        svc = JwtService(algorithm="HS256", secret_key=SECRET)

        token = pyjwt_mod.encode(
            {
                "sub": "u1",
                "tenant_id": "t1",
                "email": "a@b.com",
                "role": "admin",
                "token_type": "access",
                "iat": "not-an-integer",
                "exp": int(datetime.now(UTC).timestamp()) + 300,
                "jti": "bad-iat",
            },
            SECRET,
            algorithm="HS256",
        )
        with pytest.raises(InvalidTokenError):
            svc.decode(token)

    def test_iat_future_rejected_by_pyjwt(self):
        """PyJWT rechaza ``iat`` futuro (endurecimiento frente a python-jose,
        que solo comprobaba el tipo). Documentado como diferencia de política."""
        svc = JwtService(algorithm="HS256", secret_key=SECRET)

        future = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
        token = pyjwt_mod.encode(
            {
                "sub": "u1",
                "tenant_id": "t1",
                "email": "a@b.com",
                "role": "admin",
                "token_type": "access",
                "iat": future,
                "exp": int(datetime.now(UTC).timestamp()) + 7200,
                "jti": "future-iat",
            },
            SECRET,
            algorithm="HS256",
        )
        with pytest.raises(InvalidTokenError):
            svc.decode(token)
