"""Shared security headers middleware for aiohttp services (external, ADR-0002).

Adds standard security headers to all HTTP responses:
- Content-Security-Policy (CSP)
- Strict-Transport-Security (HSTS)
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy
- Permissions-Policy
- X-Request-ID (if correlation middleware provides it)

Usage::

    from libs.shared.security_headers import security_headers_middleware

    app = web.Application(middlewares=[security_headers_middleware()])
"""
import os
import uuid

from aiohttp import web

# Default CSP policy (restrictive but functional for a SPA).
_DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self' http://localhost:* https://localhost:*; "
    "frame-ancestors 'none'"
)

# HSTS max-age: 1 year (31536000 seconds).
_HSTS_MAX_AGE = 31536000


def security_headers_middleware(
    *,
    csp: str | None = None,
    hsts_max_age: int | None = None,
    frame_options: str = "DENY",
    referrer_policy: str = "strict-origin-when-cross-origin",
) -> web.middleware:
    """Create an aiohttp middleware that adds security headers.

    Args:
        csp: Content-Security-Policy header value. Defaults to restrictive policy.
        hsts_max_age: HSTS max-age in seconds. Defaults to 1 year.
        frame_options: X-Frame-Options value. Defaults to DENY.
        referrer_policy: Referrer-Policy value. Defaults to strict-origin-when-cross-origin.
    """
    _csp = csp or os.getenv("CSP_POLICY", _DEFAULT_CSP)
    _hsts = hsts_max_age or _HSTS_MAX_AGE

    @web.middleware
    async def middleware(request: web.Request, handler) -> web.Response:
        response = await handler(request)

        # Security headers.
        response.headers["Content-Security-Policy"] = _csp
        response.headers["Strict-Transport-Security"] = f"max-age={_hsts}"
        response.headers["X-Frame-Options"] = frame_options
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = referrer_policy
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # Request ID for tracing (if not already set by correlation middleware).
        if "X-Request-ID" not in response.headers:
            response.headers["X-Request-ID"] = request.get(
                "request_id", uuid.uuid4().hex[:16]
            )

        return response

    return middleware
