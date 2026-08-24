"""Shared security headers middleware for aiohttp services (external, ADR-0002).

Phase 14: Hardened CSP with nonce-based script loading (no unsafe-inline/eval).
Adds standard security headers to all HTTP responses:
- Content-Security-Policy (CSP) with nonce-based scripts
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

# Phase 14: Hardened CSP — nonce-based, no unsafe-inline/eval.
# Production CSP is generated per-request with a nonce; this is the template.
_CSP_TEMPLATE = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self' http://localhost:* https://localhost:*; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# Fallback CSP for responses that don't need nonce (e.g., health check).
_CSP_STATIC = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# HSTS max-age: 1 year (31536000 seconds).
_HSTS_MAX_AGE = 31536000


def generate_nonce() -> str:
    """Generate a cryptographically secure nonce for CSP."""
    return uuid.uuid4().hex[:16]


def security_headers_middleware(
    *,
    csp: str | None = None,
    hsts_max_age: int | None = None,
    frame_options: str = "DENY",
    referrer_policy: str = "strict-origin-when-cross-origin",
    use_nonce: bool = True,
) -> web.middleware:
    """Create an aiohttp middleware that adds security headers.

    Args:
        csp: Content-Security-Policy header value. Defaults to nonce-based policy.
        hsts_max_age: HSTS max-age in seconds. Defaults to 1 year.
        frame_options: X-Frame-Options value. Defaults to DENY.
        referrer_policy: Referrer-Policy value. Defaults to strict-origin-when-cross-origin.
        use_nonce: If True, generate a per-request nonce and inject it into CSP.
    """
    _hsts = hsts_max_age or _HSTS_MAX_AGE
    _csp_template = csp or os.getenv("CSP_POLICY", _CSP_TEMPLATE)

    @web.middleware
    async def middleware(request: web.Request, handler) -> web.Response:
        response = await handler(request)

        # Phase 14: Per-request nonce for script-src.
        if use_nonce and "{nonce}" in _csp_template:
            nonce = generate_nonce()
            response.headers["Content-Security-Policy"] = _csp_template.replace(
                "{nonce}", nonce
            )
            # Expose nonce to frontend JS via meta tag (handled by template).
            response.headers["X-CSP-Nonce"] = nonce
        elif use_nonce:
            # Template doesn't have nonce placeholder — use static CSP.
            response.headers["Content-Security-Policy"] = _CSP_STATIC
        else:
            response.headers["Content-Security-Policy"] = _csp_template

        # Security headers.
        response.headers["Strict-Transport-Security"] = f"max-age={_hsts}"
        response.headers["X-Frame-Options"] = frame_options
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = referrer_policy
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # Request ID for tracing (if not already set by correlation middleware).
        if "X-Request-ID" not in response.headers:
            response.headers["X-Request-ID"] = request.get(
                "request_id", uuid.uuid4().hex[:16]
            )

        return response

    return middleware
