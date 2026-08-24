"""Phase 13 — Frontend Token Security tests."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.access.cookie_auth import (
    clear_refresh_cookie,
    get_refresh_token_from_cookie,
    set_refresh_cookie,
)


def test_set_refresh_cookie_has_httponly():
    """Phase 13: refresh token cookie must be HttpOnly."""
    response = MagicMock()
    set_refresh_cookie(response, "test_token")
    response.set_cookie.assert_called_once()
    _, kwargs = response.set_cookie.call_args
    assert kwargs["httponly"] is True


def test_set_refresh_cookie_has_secure():
    """Phase 13: refresh token cookie must be Secure."""
    response = MagicMock()
    set_refresh_cookie(response, "test_token")
    _, kwargs = response.set_cookie.call_args
    assert kwargs["secure"] is True


def test_set_refresh_cookie_has_samesite_strict():
    """Phase 20.1: refresh token cookie must have SameSite=Lax.

    Lax allows same-site refresh requests while blocking cross-site CSRF.
    Strict would block same-site navigations which breaks refresh flow.
    """
    response = MagicMock()
    set_refresh_cookie(response, "test_token")
    _, kwargs = response.set_cookie.call_args
    assert kwargs["samesite"] == "Lax"


def test_set_refresh_cookie_has_correct_path():
    """Phase 13: refresh token cookie must be scoped to refresh endpoint."""
    response = MagicMock()
    set_refresh_cookie(response, "test_token")
    _, kwargs = response.set_cookie.call_args
    assert kwargs["path"] == "/api/v1/auth/refresh"


def test_set_refresh_cookie_has_max_age():
    """Phase 13: refresh token cookie must have max_age."""
    response = MagicMock()
    set_refresh_cookie(response, "test_token", max_age=3600)
    _, kwargs = response.set_cookie.call_args
    assert kwargs["max_age"] == 3600


def test_clear_refresh_cookie():
    """Phase 13: logout must clear the refresh token cookie."""
    response = MagicMock()
    clear_refresh_cookie(response)
    response.del_cookie.assert_called_once_with(
        "refresh_token", path="/api/v1/auth/refresh"
    )


def test_get_refresh_token_from_cookie():
    """Phase 13: server can extract refresh token from cookie."""
    request = MagicMock()
    request.cookies = {"refresh_token": "test_token_123"}
    token = get_refresh_token_from_cookie(request)
    assert token == "test_token_123"


def test_get_refresh_token_from_cookie_missing():
    """Phase 13: missing cookie returns None."""
    request = MagicMock()
    request.cookies = {}
    token = get_refresh_token_from_cookie(request)
    assert token is None
