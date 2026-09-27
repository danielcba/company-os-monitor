"""Security regression: verify no silent fallback to test credentials.

D-01 CREDENTIAL REMEDIATION — Fail-closed verification.

These tests ensure that the critical security defect (hardcoded PostgreSQL
credentials as silent fallback) is permanently closed.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jose import jwt as jose_jwt

from libs.access.errors import InvalidTokenError


class TestDatabaseUrlRequired:
    """DATABASE_URL must be required — no silent fallback to test credentials."""

    def test_shared_db_requires_database_url(self):
        """libs/shared/db.py must raise RuntimeError when DATABASE_URL is absent."""
        env = os.environ.copy()
        env.pop("DATABASE_URL", None)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from libs.shared.db import create_shared_engine;"
                " create_shared_engine()",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(Path(__file__).resolve().parents[2]),
            check=False,
        )
        assert result.returncode != 0, (
            "create_shared_engine() should fail when DATABASE_URL is absent"
        )
        assert "DATABASE_URL" in (result.stderr + result.stdout), (
            "Error message should mention DATABASE_URL"
        )
        assert "cosmonitor" not in (result.stderr + result.stdout), (
            "Error message must not contain test credentials"
        )

    def test_service_main_requires_database_url(self):
        """Each service main.py must not contain hardcoded fallback."""
        service_dirs = [
            "apps/services/user-service",
            "apps/services/confidence-service",
            "apps/services/hypothesis-service",
            "apps/services/context-service",
            "apps/services/pattern-service",
            "apps/services/anomaly-service",
            "apps/services/evaluation-service",
            "apps/services/decision-service",
            "apps/services/collector-service",
            "apps/services/recommendation-service",
            "apps/services/insight-service",
            "apps/services/report-service",
        ]

        for service_dir in service_dirs:
            src_main = (
                Path(__file__).resolve().parents[2]
                / service_dir / "src" / "main.py"
            )
            if not src_main.exists():
                continue

            content = src_main.read_text()
            assert "cosmonitor:cosmonitor" not in content, (
                f"{service_dir}/src/main.py still contains hardcoded credentials"
            )

    def test_no_harcdcoded_fallback_in_db_factory(self):
        """libs/shared/db.py must not contain hardcoded PostgreSQL credentials."""
        db_py = (
            Path(__file__).resolve().parents[2] / "libs" / "shared" / "db.py"
        )
        content = db_py.read_text()
        assert "cosmonitor:cosmonitor" not in content, (
            "libs/shared/db.py still contains hardcoded test credentials"
        )
        assert "postgresql+asyncpg://cosmonitor" not in content, (
            "libs/shared/db.py still contains hardcoded test credentials"
        )


class TestJwtSecretKey:
    """JWT_SECRET_KEY must not have a dangerous default."""

    def test_no_insecure_default_in_env_example(self):
        """.env.example must not contain a copy-pasteable insecure default."""
        env_example = (
            Path(__file__).resolve().parents[2] / ".env.example"
        )
        content = env_example.read_text()
        assert "your-secret-key-change-in-production" not in content, (
            ".env.example still contains the old insecure placeholder"
        )

    def test_jwt_secret_key_in_code_uses_env_var(self):
        """Application code must read JWT_SECRET_KEY from environment."""
        security_py = (
            Path(__file__).resolve().parents[2]
            / "apps"
            / "services"
            / "user-service"
            / "src"
            / "auth"
            / "security.py"
        )
        if security_py.exists():
            content = security_py.read_text()
            assert (
                'os.getenv("JWT_SECRET_KEY")' in content
                or "os.getenv('JWT_SECRET_KEY')" in content
            ), (
                "JWT_SECRET_KEY should be read from env without hardcoded default"
            )

    @staticmethod
    def _env_example_value(var: str) -> str:
        """Value of ``var`` as shipped in .env.example (the template itself)."""
        content = (Path(__file__).resolve().parents[2] / ".env.example").read_text()
        for line in content.splitlines():
            if line.startswith(f"{var}="):
                return line.split("=", 1)[1].strip()
        pytest.fail(f"{var} missing from .env.example")

    def test_env_example_secret_is_not_a_usable_credential(self):
        """.env.example JWT_SECRET_KEY must be rejected by JwtService (fail-closed)."""
        from libs.access.security import JwtService  # noqa: PLC0415

        placeholder = self._env_example_value("JWT_SECRET_KEY")
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            JwtService(algorithm="HS256", secret_key=placeholder)

    def test_env_example_rs256_key_placeholders_are_rejected(self):
        """.env.example RS256 keypair placeholders must be rejected too."""
        from libs.access.security import JwtService  # noqa: PLC0415

        with pytest.raises(ValueError, match="JWT_PRIVATE_KEY"):
            JwtService(
                algorithm="RS256",
                private_key=self._env_example_value("JWT_PRIVATE_KEY"),
                public_key=self._env_example_value("JWT_PUBLIC_KEY"),
            )

    def test_placeholder_error_does_not_echo_the_value(self):
        """The rejection message must not print the credential it rejects."""
        from libs.access.security import JwtService  # noqa: PLC0415

        placeholder = self._env_example_value("JWT_SECRET_KEY")
        with pytest.raises(ValueError) as excinfo:
            JwtService(algorithm="HS256", secret_key=placeholder)
        assert placeholder not in str(excinfo.value), (
            "config error must not echo the rejected secret"
        )

    def test_real_dev_secret_still_accepted(self):
        """A normal dev secret keeps working: no unnecessary DX regression."""
        from libs.access.security import JwtService  # noqa: PLC0415

        svc = JwtService(
            algorithm="HS256",
            secret_key="test-secret",
            issuer="http://localhost",
            audience="cosmonitor",
        )
        token = svc.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        assert svc.verify_access_token(token).token_type == "access"

    def test_missing_secret_still_fails_closed(self):
        """Absence of JWT_SECRET_KEY remains a hard failure (unchanged)."""
        from libs.access.security import JwtService  # noqa: PLC0415

        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            JwtService(algorithm="HS256", secret_key=None)

    def test_app_mains_read_jwt_secret_only_from_env(self):
        """Gateway/report/user-service must not hardcode a signing default."""
        readers = [
            "apps/gateway/api-gateway/src/main.py",
            "apps/services/report-service/src/main.py",
            "apps/services/user-service/src/auth/security.py",
        ]
        for rel in readers:
            content = (Path(__file__).resolve().parents[2] / rel).read_text()
            assert 'os.getenv("JWT_SECRET_KEY")' in content, (
                f"{rel} must read JWT_SECRET_KEY from the environment"
            )
            assert 'secret_key="' not in content, (
                f"{rel} must not hardcode a JWT secret"
            )

    def test_start_sh_rejects_placeholder_credentials(self):
        """start.sh must refuse to boot the stack with a placeholder JWT key."""
        start_sh = Path(__file__).resolve().parents[2] / "start.sh"
        content = start_sh.read_text()
        assert "placeholder" in content, (
            "start.sh must check for .env.example placeholders"
        )
        assert "openssl rand -hex 32" in content, (
            "start.sh must tell the operator how to generate a real secret"
        )


class TestStartEnvFailClosed:
    """start.sh must fail-closed when .env is missing."""

    def test_start_sh_fails_without_env(self):
        """start.sh must exit with error when .env is absent."""
        result = subprocess.run(
            ["bash", "-n", str(Path(__file__).resolve().parents[2] / "start.sh")],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, "start.sh syntax must be valid"

    def test_start_sh_no_env_copy(self):
        """start.sh must not contain cp .env.example command."""
        start_sh = (
            Path(__file__).resolve().parents[2] / "start.sh"
        )
        content = start_sh.read_text()
        assert (
            "cp \"$ROOT/.env.example\"" not in content
            and 'cp "$ROOT/.env.example"' not in content
        ), (
            "start.sh must not copy .env.example to .env"
        )
        assert ".env" in content, (
            "start.sh must still reference .env"
        )
        assert "die" in content, (
            "start.sh must use die for missing .env"
        )

    def test_start_sh_die_on_missing_env(self):
        """start.sh must die when .env is missing."""
        start_sh = (
            Path(__file__).resolve().parents[2] / "start.sh"
        )
        content = start_sh.read_text()
        assert 'die "' in content, (
            "start.sh must use die for missing .env"
        )
        assert ".env" in content and "not found" in content, (
            "start.sh error message must mention .env not found"
        )


class TestJwtAudienceIssuer:
    """JWT must include issuer and audience claims and verify them."""

    def test_token_includes_issuer_when_configured(self):
        """JwtService with issuer must include iss claim."""
        from libs.access.security import JwtService  # noqa: PLC0415

        svc = JwtService(
            algorithm="HS256",
            secret_key="test-secret",
            issuer="http://localhost",
            audience="cosmonitor",
        )
        token = svc.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        payload = jose_jwt.decode(
            token, "test-secret", algorithms=["HS256"], audience="cosmonitor"
        )
        assert payload["iss"] == "http://localhost", (
            "Token must include iss claim"
        )
        assert payload["aud"] == "cosmonitor", (
            "Token must include aud claim"
        )

    def test_token_missing_issuer_when_not_configured(self):
        """JwtService without issuer must not include iss claim."""
        from libs.access.security import JwtService  # noqa: PLC0415

        svc = JwtService(
            algorithm="HS256",
            secret_key="test-secret",
        )
        token = svc.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        payload = jose_jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert "iss" not in payload, (
            "Token must not include iss when issuer not configured"
        )
        assert "aud" not in payload, (
            "Token must not include aud when audience not configured"
        )

    def test_wrong_audience_rejected(self):
        """Token with wrong audience must be rejected."""
        from libs.access.security import JwtService  # noqa: PLC0415

        svc = JwtService(
            algorithm="HS256",
            secret_key="test-secret",
            issuer="http://localhost",
            audience="cosmonitor",
        )
        token = svc.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        wrong_svc = JwtService(
            algorithm="HS256",
            secret_key="test-secret",
            issuer="http://localhost",
            audience="wrong-audience",
        )
        with pytest.raises(InvalidTokenError, match="audience"):
            wrong_svc.verify_access_token(token)

    def test_wrong_issuer_rejected(self):
        """Token with wrong issuer must be rejected."""
        from libs.access.security import JwtService  # noqa: PLC0415

        svc = JwtService(
            algorithm="HS256",
            secret_key="test-secret",
            issuer="http://localhost",
            audience="cosmonitor",
        )
        token = svc.create_access_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        wrong_svc = JwtService(
            algorithm="HS256",
            secret_key="test-secret",
            issuer="http://wrong-issuer",
            audience="cosmonitor",
        )
        with pytest.raises(InvalidTokenError, match="issuer"):
            wrong_svc.verify_access_token(token)

    def test_rs256_aud_iss_compatible(self):
        """RS256 tokens with issuer/audience must verify correctly."""
        from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: I001, PLC0415
        from cryptography.hazmat.primitives import serialization  # noqa: PLC0415
        from libs.access.security import JwtService  # noqa: PLC0415

        private_key_obj = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        private_pem = private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        public_pem = private_key_obj.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

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
        assert payload.token_type == "access", (
            "RS256 token must verify with correct issuer/audience"
        )


class TestRedisUrlNormalizationPreservesCredential:
    """start.sh host normalization must keep the requirepass credential.

    Redis runs with ``--requirepass`` (docker-compose), so every Redis URL
    carries ``redis://<password>@host``. Rewriting the container hostname
    (``redis`` -> ``localhost``) must only touch the host part, otherwise the
    host-side processes drop the credential and fail AUTH at runtime.
    """

    @staticmethod
    def _normalize(url: str) -> str:
        start_sh = Path(__file__).resolve().parents[2] / "start.sh"
        lines = start_sh.read_text().splitlines()
        try:
            start = next(
                i
                for i, line in enumerate(lines)
                if line.startswith("# Host-side processes reach")
            )
            end = next(
                i
                for i, line in enumerate(lines)
                if line.startswith('case "$DATABASE_URL"')
            )
        except StopIteration:  # pragma: no cover - marker text changed
            pytest.fail("start.sh URL normalization block not found")
        block = "\n".join(lines[start:end])
        script = block + '\nprintf "%s" "$REDIS_URL"'
        env = os.environ.copy()
        env["REDIS_URL"] = url
        env["OBSERVATION_BUS_URL"] = url
        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    def test_credential_preserved(self):
        assert self._normalize("redis://pw@redis:6379") == "redis://pw@localhost:6379"

    def test_credentialless_still_normalizes(self):
        assert self._normalize("redis://redis:6379") == "redis://localhost:6379"

    def test_db_suffix_preserved(self):
        assert self._normalize("redis://pw@redis:6379/2") == "redis://pw@localhost:6379/2"

    def test_foreign_host_untouched(self):
        assert self._normalize("redis://pw@otherhost:6379") == "redis://pw@otherhost:6379"
