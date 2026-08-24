"""Tests for security headers middleware (Phase 14 — CSP hardening)."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from libs.shared.security_headers import generate_nonce, security_headers_middleware


async def test_security_headers_added():
    middleware = security_headers_middleware()
    request = MagicMock()
    request.get = MagicMock(return_value=None)
    handler = AsyncMock(return_value=MagicMock(headers={}))
    response = await middleware(request, handler)
    assert "Content-Security-Policy" in response.headers
    assert "Strict-Transport-Security" in response.headers
    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Referrer-Policy" in response.headers
    assert "Permissions-Policy" in response.headers


async def test_nonce_generated_when_use_nonce_true():
    middleware = security_headers_middleware(use_nonce=True)
    request = MagicMock()
    request.get = MagicMock(return_value=None)
    handler = AsyncMock(return_value=MagicMock(headers={}))
    response = await middleware(request, handler)
    csp = response.headers["Content-Security-Policy"]
    # Phase 14: script-src must NOT have unsafe-inline (style-src can).
    script_src = csp.split("script-src")[1].split(";")[0]
    assert "unsafe-inline" not in script_src
    assert "unsafe-eval" not in script_src
    assert "nonce-" in script_src
    assert "X-CSP-Nonce" in response.headers


async def test_static_csp_when_use_nonce_false():
    middleware = security_headers_middleware(use_nonce=False, csp="default-src 'self'")
    request = MagicMock()
    request.get = MagicMock(return_value=None)
    handler = AsyncMock(return_value=MagicMock(headers={}))
    response = await middleware(request, handler)
    assert response.headers["Content-Security-Policy"] == "default-src 'self'"


async def test_custom_hsts():
    middleware = security_headers_middleware(hsts_max_age=63072000)
    request = MagicMock()
    request.get = MagicMock(return_value=None)
    handler = AsyncMock(return_value=MagicMock(headers={}))
    response = await middleware(request, handler)
    assert "max-age=63072000" in response.headers["Strict-Transport-Security"]


async def test_request_id_preserved():
    middleware = security_headers_middleware()
    request = MagicMock()
    request.get = MagicMock(return_value="existing-id")
    handler = AsyncMock(return_value=MagicMock(headers={}))
    response = await middleware(request, handler)
    assert response.headers["X-Request-ID"] == "existing-id"


def test_generate_nonce_returns_hex():
    nonce = generate_nonce()
    assert len(nonce) == 16  # noqa: PLR2004 - nonce length is 16 chars
    int(nonce, 16)  # Must be valid hex.
