"""Shared request middleware for timeouts and correlation IDs (shared utility).

Provides aiohttp middleware for:
- Request timeout enforcement
- Correlation ID generation/propagation (X-Request-ID)
- Structured request logging

Usage::

    from libs.shared.middleware import request_timeout_middleware, correlation_middleware

    app = web.Application(middlewares=[
        correlation_middleware(),
        request_timeout_middleware(timeout_seconds=30),
    ])
"""
import logging
import time
import uuid

from aiohttp import web

logger = logging.getLogger(__name__)


def correlation_middleware() -> web.middleware:
    """Middleware that generates or propagates a correlation ID (X-Request-ID).

    If the client sends an X-Request-ID header, it is propagated.
    Otherwise, a new UUID is generated for tracing.
    """

    @web.middleware
    async def middleware(request: web.Request, handler) -> web.Response:
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:16])
        request["request_id"] = request_id

        start = time.monotonic()
        try:
            response = await handler(request)
            elapsed_ms = (time.monotonic() - start) * 1000
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"

            logger.info(
                "%s %s -> %s (%.1fms) [%s]",
                request.method,
                request.path,
                response.status,
                elapsed_ms,
                request_id,
            )
            return response
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.exception(
                "%s %s -> ERROR (%.1fms) [%s]",
                request.method,
                request.path,
                elapsed_ms,
                request_id,
            )
            raise

    return middleware


def request_timeout_middleware(timeout_seconds: float = 30.0) -> web.middleware:
    """Middleware that enforces a per-request timeout.

    If the handler does not complete within the timeout, a 504 is returned.
    """

    @web.middleware
    async def middleware(request: web.Request, handler) -> web.Response:
        try:
            return await asyncio.wait_for(handler(request), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                "Request timeout: %s %s after %.1fs",
                request.method,
                request.path,
                timeout_seconds,
            )
            return web.json_response(
                {"error": "Request timeout"},
                status=504,
            )

    return middleware


# Lazy import to avoid circular imports at module level.
import asyncio  # noqa: E402
