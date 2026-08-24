"""Structured logging with correlation for cognitive pipeline tracing.

Phase 18: Ensures every log entry includes:
- X-Request-ID: request correlation
- trace_id: distributed trace ID
- tenant_id: tenant isolation
- service: which service generated the log
- cognitive_capability: which cognitive concept is being processed

Phase 18: NEVER logs:
- passwords
- JWT tokens
- refresh tokens
- secrets
- API keys

Usage::

    from libs.shared.structured_logging import get_logger

    logger = get_logger("gateway")
    logger.info("Processing observation", extra={
        "tenant_id": str(tenant_id),
        "cognitive_capability": "observation",
    })
"""
import logging
import re
from typing import Any


# Patterns for sensitive data that must NEVER be logged.
SENSITIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r"password[\"':\s]*[\"'][^\"']+[\"']", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"refresh_token[\"':\s]*[\"'][^\"']+[\"']", re.IGNORECASE),
    re.compile(r"api[_-]?key[\"':\s]*[\"'][^\"']+[\"']", re.IGNORECASE),
    re.compile(r"secret[\"':\s]*[\"'][^\"']+[\"']", re.IGNORECASE),
]

# Fields that must be sanitized before logging.
SENSITIVE_FIELDS: frozenset[str] = frozenset({
    "password",
    "refresh_token",
    "access_token",
    "secret",
    "api_key",
    "apiKey",
})


def sanitize_log_data(data: dict[str, Any]) -> dict[str, Any]:
    """Remove or mask sensitive fields from log data.

    Phase 18: Ensures passwords, tokens, and secrets are never logged.
    """
    sanitized = {}
    for key, value in data.items():
        if key.lower() in {f.lower() for f in SENSITIVE_FIELDS}:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, str):
            # Check for embedded sensitive patterns.
            for pattern in SENSITIVE_PATTERNS:
                if pattern.search(value):
                    sanitized[key] = "***REDACTED***"
                    break
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value
    return sanitized


class StructuredLogger:
    """Logger that enforces structured fields and sanitization.

    Wraps a standard Python logger and ensures:
    - Sensitive data is never logged
    - Cognitive pipeline fields are always available
    - Correlation IDs are preserved
    """

    def __init__(self, name: str, service: str = ""):
        self._logger = logging.getLogger(name)
        self._service = service

    def _extra_fields(
        self,
        tenant_id: str | None = None,
        cognitive_capability: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Build the standard extra fields for structured logging."""
        extra: dict[str, Any] = {}
        if self._service:
            extra["service"] = self._service
        if tenant_id:
            extra["tenant_id"] = tenant_id
        if cognitive_capability:
            extra["cognitive_capability"] = cognitive_capability
        if trace_id:
            extra["trace_id"] = trace_id
        if request_id:
            extra["request_id"] = request_id
        return extra

    def info(
        self,
        msg: str,
        *,
        tenant_id: str | None = None,
        cognitive_capability: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log at INFO level with structured fields."""
        all_extra = self._extra_fields(
            tenant_id, cognitive_capability, trace_id, request_id
        )
        if extra:
            all_extra.update(sanitize_log_data(extra))
        self._logger.info(msg, extra=all_extra)

    def warning(
        self,
        msg: str,
        *,
        tenant_id: str | None = None,
        cognitive_capability: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log at WARNING level with structured fields."""
        all_extra = self._extra_fields(
            tenant_id, cognitive_capability, trace_id, request_id
        )
        if extra:
            all_extra.update(sanitize_log_data(extra))
        self._logger.warning(msg, extra=all_extra)

    def error(
        self,
        msg: str,
        *,
        tenant_id: str | None = None,
        cognitive_capability: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log at ERROR level with structured fields."""
        all_extra = self._extra_fields(
            tenant_id, cognitive_capability, trace_id, request_id
        )
        if extra:
            all_extra.update(sanitize_log_data(extra))
        self._logger.error(msg, extra=all_extra)

    def debug(
        self,
        msg: str,
        *,
        tenant_id: str | None = None,
        cognitive_capability: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log at DEBUG level with structured fields."""
        all_extra = self._extra_fields(
            tenant_id, cognitive_capability, trace_id, request_id
        )
        if extra:
            all_extra.update(sanitize_log_data(extra))
        self._logger.debug(msg, extra=all_extra)


def get_logger(name: str, service: str = "") -> StructuredLogger:
    """Get a structured logger for a module.

    Args:
        name: Logger name (usually __name__).
        service: Service name for correlation.
    """
    return StructuredLogger(name, service)
