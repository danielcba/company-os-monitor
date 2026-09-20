"""Security regression: verify no silent fallback to test credentials.

D-01 CREDENTIAL REMEDIATION — Fail-closed verification.

These tests ensure that the critical security defect (hardcoded PostgreSQL
credentials as silent fallback) is permanently closed.
"""
import os
import subprocess
import sys
from pathlib import Path


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
