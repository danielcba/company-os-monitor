"""CSRF protection middleware for aiohttp services (Phase 20.1).

Provides Origin/Referer validation on state-changing endpoints that use
cookies (refresh, logout). SameSite=Lax on the refresh cookie blocks
cross-site POST/PUT/DELETE, but Origin/Referer validation adds defense
in depth against same-site request forgery.

CSRF Model:
- SameSite=Lax blocks cross-site state-changing requests (primary defense)
- Origin/Referer validation blocks same-origin forgery (defense in depth)
- No CSRF token needed — the refresh cookie is HttpOnly and path-scoped

Usage::

    from libs.access.csrf import csrf_protection_middleware

    app = web.Application(middlewares=[csrf_protection_middleware()])
"""
import logging
from urllib.parse import urlparse

from aiohttp import web

logger = logging.getLogger(__name__)

# Paths that require CSRF protection (state-changing, cookie-authenticated).
_CSRF_PROTECTED_PATHS = frozenset({
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
})


def _get_origin(request: web.Request) -> str | None:
    """Extract Origin header (preferred) or construct from Referer."""
    origin = request.headers.get("Origin")
    if origin:
        return origin
    referer = request.headers.get("Referer")
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return None


def _get_expected_origin(request: web.Request) -> str:
    """Build the expected origin from the request's own scheme and host."""
    scheme = request.headers.get("X-Forwarded-Proto", "http")
    host = request.headers.get("Host", "localhost")
    return f"{scheme}://{host}"


def csrf_protection_middleware(
    *,
    allowed_origins: list[str] | None = None,
) -> web.middleware:
    """Create an aiohttp middleware that validates Origin/Referer on
    state-changing endpoints.

    Args:
        allowed_origins: Additional allowed origins beyond the request's
            own origin. Useful for development (e.g., Vite dev server).

    Returns:
        An aiohttp middleware function.
    """
    _extra_origins = set(allowed_origins or [])

    @web.middleware
    async def middleware(request: web.Request, handler) -> web.Response:
        if request.path not in _CSRF_PROTECTED_PATHS:
            return await handler(request)

        # SameSite=Lax already blocks cross-site POST. This is defense in depth.
        origin = _get_origin(request)
        expected = _get_expected_origin(request)

        if origin is None:
            # No Origin/Referer header: could be a same-site form submission
            # or a non-browser client. Allow — the cookie path scoping and
            # SameSite=Lax provide the primary defense.
            return await handler(request)

        if origin == expected:
            return await handler(request)

        if origin in _extra_origins:
            return await handler(request)

        logger.warning(
            "CSRF rejected: origin=%s expected=%s path=%s",
            origin,
            expected,
            request.path,
        )
        raise web.HTTPForbidden(
            text='{"error": "CSRF validation failed: origin mismatch"}',
            content_type="application/json",
        )

    return middleware
