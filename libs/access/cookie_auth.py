"""Phase 13 — Frontend Token Security middleware.

Provides cookie-based token storage as an alternative to localStorage.
The access token stays in memory (needed for Authorization header), but the
refresh token is moved to an HttpOnly cookie.

Phase 20.1: Cookie attributes hardened:
- HttpOnly: true (JS-inaccessible)
- Secure: true (HTTPS-only in production)
- SameSite: Lax (allows same-site refresh requests)
- Path: /api/v1/auth/refresh (scoped to refresh endpoint)
- Max-Age: 604800 (7 days)

Usage:
    # Backend sets the cookie on login/refresh
    set_refresh_cookie(response, refresh_token)

    # Frontend reads access token from response body (in-memory only)
    # Frontend does NOT store refresh token in localStorage
"""
from dataclasses import dataclass

from aiohttp import web


@dataclass(frozen=True, slots=True)
class RefreshCookieConfig:
    """Configuration for refresh token cookie attributes.

    Immutable to ensure consistent security posture across requests.
    """

    secure: bool = True
    samesite: str = "Lax"
    max_age: int = 604800  # 7 days
    path: str = "/api/v1/auth/refresh"


DEFAULT_REFRESH_COOKIE_CONFIG = RefreshCookieConfig()


def set_refresh_cookie(
    response: web.Response,
    refresh_token: str,
    *,
    config: RefreshCookieConfig = DEFAULT_REFRESH_COOKIE_CONFIG,
) -> None:
    """Set refresh token as HttpOnly cookie.

    Args:
        response: The aiohttp response to set the cookie on.
        refresh_token: The refresh token value.
        config: Cookie configuration (secure, samesite, max_age, path).
    """
    response.set_cookie(
        "refresh_token",
        refresh_token,
        secure=config.secure,
        httponly=True,
        samesite=config.samesite,
        max_age=config.max_age,
        path=config.path,
    )


def clear_refresh_cookie(response: web.Response) -> None:
    """Clear the refresh token cookie (on logout)."""
    response.del_cookie("refresh_token", path="/api/v1/auth/refresh")


def get_refresh_token_from_cookie(request: web.Request) -> str | None:
    """Extract refresh token from HttpOnly cookie.

    This is server-side only — JavaScript cannot access HttpOnly cookies.
    """
    return request.cookies.get("refresh_token")
