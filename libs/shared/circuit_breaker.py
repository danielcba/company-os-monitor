"""Circuit breaker for DB calls and external dependencies (shared utility).

Provides a simple circuit breaker pattern to prevent cascade failures when
downstream services or database are under load.

States:
    CLOSED: Normal operation. Requests pass through.
    OPEN: Failure threshold exceeded. Requests are rejected immediately.
    HALF_OPEN: After reset_timeout, one test request is allowed through.

Usage::

    from libs.shared.circuit_breaker import CircuitBreaker

    breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)
    result = await breaker.call(db_query, arg1, arg2)
"""
import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple async circuit breaker for protecting against cascade failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        name: str = "default",
    ):
        """
        Args:
            failure_threshold: Number of consecutive failures before opening.
            reset_timeout: Seconds to wait before trying half-open.
            name: Name for logging.
        """
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._name = name
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_attempts = 0

    @property
    def state(self) -> CircuitState:
        """Current circuit state (auto-transitions from OPEN to HALF_OPEN)."""
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self._reset_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_attempts = 0
        return self._state

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function through the circuit breaker.

        Raises CircuitBreakerOpenError if the circuit is open.
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit '{self._name}' is open; "
                f"retry after {self._reset_timeout}s"
            )

        if current_state == CircuitState.HALF_OPEN:
            self._half_open_attempts += 1
            if self._half_open_attempts > 1:
                raise CircuitBreakerOpenError(
                    f"Circuit '{self._name}' is half-open; "
                    f"waiting for test request"
                )

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info("Circuit '%s' recovered; closing", self._name)
            self._state = CircuitState.CLOSED
            self._failure_count = 0
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning("Circuit '%s' test failed; re-opening", self._name)
            self._state = CircuitState.OPEN
        elif self._failure_count >= self._failure_threshold:
            logger.warning(
                "Circuit '%s' opened after %d failures",
                self._name,
                self._failure_count,
            )
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Manually reset the circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is open and rejecting requests."""
