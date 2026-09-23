"""Security regression: verify no silent fallback to test credentials.

D-01 CREDENTIAL REMEDIATION — Fail-closed verification.

These tests ensure that the critical security defect (hardcoded PostgreSQL
credentials as silent fallback) is permanently closed.
"""
import os
import subprocess
import sys
from pathlib import Path

from jose import jwt as jose_jwt


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
        try:
            wrong_svc.verify_access_token(token)
            raise AssertionError("Wrong audience should be rejected")  # noqa: TRY301,TRY003
        except Exception:  # noqa: BLE001
            pass

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
        try:
            wrong_svc.verify_access_token(token)
            raise AssertionError("Wrong issuer should be rejected")  # noqa: TRY301,TRY003
        except Exception:  # noqa: BLE001
            pass

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
