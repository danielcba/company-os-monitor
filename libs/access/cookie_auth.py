"""Phase 13 — Frontend Token Security middleware.

Provides cookie-based token storage as an alternative to localStorage.
The access token stays in memory (needed for Authorization header), but the
refresh token is moved to an HttpOnly cookie.

Usage:
    # Backend sets the cookie on login/refresh
    set_refresh_cookie(response, refresh_token)

    # Frontend reads access token from response body (in-memory only)
    # Frontend does NOT store refresh token in localStorage
"""
from aiohttp import web


def set_refresh_cookie(
    response: web.Response,
    refresh_token: str,
    *,
    secure: bool = True,
    samesite: str = "Strict",
    max_age: int = 604800,  # 7 days
    path: str = "/api/v1/auth/refresh",
) -> None:
    """Set refresh token as HttpOnly cookie.

    Args:
        response: The aiohttp response to set the cookie on.
        refresh_token: The refresh token value.
        secure: If True, cookie is only sent over HTTPS.
        samesite: SameSite attribute (Strict/Lax/None).
        max_age: Cookie lifetime in seconds.
        path: Cookie path scope.
    """
    response.set_cookie(
        "refresh_token",
        refresh_token,
        secure=secure,
        httponly=True,
        samesite=samesite,
        max_age=max_age,
        path=path,
    )


def clear_refresh_cookie(response: web.Response) -> None:
    """Clear the refresh token cookie (on logout)."""
    response.del_cookie("refresh_token", path="/api/v1/auth/refresh")


def get_refresh_token_from_cookie(request: web.Request) -> str | None:
    """Extract refresh token from HttpOnly cookie.

    This is server-side only — JavaScript cannot access HttpOnly cookies.
    """
    return request.cookies.get("refresh_token")
