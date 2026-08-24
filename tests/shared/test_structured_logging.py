"""Phase 18 — Observability/Correlation tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.shared.structured_logging import (
    StructuredLogger,
    sanitize_log_data,
)


def test_password_is_redacted():
    """Phase 18: passwords must never be logged."""
    data = {"password": "secret123", "username": "admin"}
    sanitized = sanitize_log_data(data)
    assert sanitized["password"] == "***REDACTED***"
    assert sanitized["username"] == "admin"


def test_refresh_token_is_redacted():
    """Phase 18: refresh tokens must never be logged."""
    data = {"refresh_token": "eyJhbGciOiJIUzI1NiIs..."}
    sanitized = sanitize_log_data(data)
    assert sanitized["refresh_token"] == "***REDACTED***"


def test_access_token_is_redacted():
    """Phase 18: access tokens must never be logged."""
    data = {"access_token": "eyJhbGciOiJIUzI1NiIs..."}
    sanitized = sanitize_log_data(data)
    assert sanitized["access_token"] == "***REDACTED***"


def test_api_key_is_redacted():
    """Phase 18: API keys must never be logged."""
    data = {"api_key": "sk-1234567890"}
    sanitized = sanitize_log_data(data)
    assert sanitized["api_key"] == "***REDACTED***"


def test_secret_is_redacted():
    """Phase 18: secrets must never be logged."""
    data = {"secret": "my-secret-value"}
    sanitized = sanitize_log_data(data)
    assert sanitized["secret"] == "***REDACTED***"


def test_bearer_token_in_string_is_redacted():
    """Phase 18: Bearer tokens embedded in strings must be redacted."""
    data = {"authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}
    sanitized = sanitize_log_data(data)
    assert sanitized["authorization"] == "***REDACTED***"


def test_non_sensitive_data_preserved():
    """Phase 18: non-sensitive data must be preserved."""
    data = {
        "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
        "cognitive_capability": "observation",
        "message": "Processing observation",
    }
    sanitized = sanitize_log_data(data)
    assert sanitized["tenant_id"] == data["tenant_id"]
    assert sanitized["cognitive_capability"] == data["cognitive_capability"]
    assert sanitized["message"] == data["message"]


def test_structured_logger_has_standard_fields():
    """Phase 18: structured logger must support standard fields."""
    logger = StructuredLogger("test", service="gateway")
    assert logger._service == "gateway"
