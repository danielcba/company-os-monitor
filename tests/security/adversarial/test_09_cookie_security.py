"""09 - Cookie Security: refresh token cookie attributes.

Verifies: HttpOnly, Secure, SameSite=Strict, correct path, max_age.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from unittest.mock import MagicMock

from libs.access.cookie_auth import (
    clear_refresh_cookie,
    get_refresh_token_from_cookie,
    set_refresh_cookie,
)


def test_cookie_httponly():
    """Refresh cookie MUST be HttpOnly (JS cannot access)."""
    response = MagicMock()
    set_refresh_cookie(response, "token")
    _, kwargs = response.set_cookie.call_args
    assert kwargs["httponly"] is True


def test_cookie_secure():
    """Refresh cookie MUST be Secure (HTTPS only)."""
    response = MagicMock()
    set_refresh_cookie(response, "token")
    _, kwargs = response.set_cookie.call_args
    assert kwargs["secure"] is True


def test_cookie_samesite_strict():
    """Refresh cookie MUST have SameSite=Strict."""
    response = MagicMock()
    set_refresh_cookie(response, "token")
    _, kwargs = response.set_cookie.call_args
    assert kwargs["samesite"] == "Strict"


def test_cookie_scoped_to_refresh_path():
    """Refresh cookie MUST be scoped to /api/v1/auth/refresh."""
    response = MagicMock()
    set_refresh_cookie(response, "token")
    _, kwargs = response.set_cookie.call_args
    assert kwargs["path"] == "/api/v1/auth/refresh"


EXPECTED_MAX_AGE = 3600


def test_cookie_has_max_age():
    """Refresh cookie MUST have a max_age."""
    response = MagicMock()
    set_refresh_cookie(response, "token", max_age=EXPECTED_MAX_AGE)
    _, kwargs = response.set_cookie.call_args
    assert kwargs["max_age"] == EXPECTED_MAX_AGE


def test_logout_clears_cookie():
    """Logout MUST clear the refresh cookie."""
    response = MagicMock()
    clear_refresh_cookie(response)
    response.del_cookie.assert_called_once_with(
        "refresh_token", path="/api/v1/auth/refresh"
    )


def test_extract_token_from_cookie():
    """Server can extract refresh token from HttpOnly cookie."""
    request = MagicMock()
    request.cookies = {"refresh_token": "my_token"}
    assert get_refresh_token_from_cookie(request) == "my_token"


def test_missing_cookie_returns_none():
    """Missing cookie returns None."""
    request = MagicMock()
    request.cookies = {}
    assert get_refresh_token_from_cookie(request) is None
