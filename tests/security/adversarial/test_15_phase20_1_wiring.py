"""Phase 20.1 — Runtime Wiring & Production Hardening Tests.

Covers:
1. P0: ConfidenceStore injection in GatewayService
2. P1: Frontend HttpOnly refresh cookie (no localStorage)
3. P1: JWT revocation consistency across services

These tests verify that the runtime wiring matches the architecture
and that security controls are fail-closed.
"""
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "gateway" / "api-gateway"))

from libs.access.errors import InvalidTokenError
from libs.access.security import JwtService
from libs.access.token_blacklist import SecurityControlUnavailable

SECRET = "test-secret-phase20-1"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
_root = Path(__file__).resolve().parents[3]  # company-os-monitor root


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


# ============================================================
# P0: ConfidenceStore injection in GatewayService
# ============================================================


class FakeConfidenceStore:
    """Fake confidence store that implements ConfidenceStoreAdapter protocol."""

    def __init__(self, records=None):
        self._records = records or {}
        self.get_called = False

    async def get_confidence_for_boundary(
        self,
        *,
        tenant_id: str,
        confidence_id: str,
        expected_target_type: str,
        expected_target_id: str | None = None,
    ) -> dict | None:
        self.get_called = True
        key = (tenant_id, confidence_id)
        record = self._records.get(key)
        if record is None:
            return None
        if record.get("target_type") != expected_target_type:
            return None
        if expected_target_id and record.get("target_id") != expected_target_id:
            return None
        return record


class FakeBlacklist:
    """Fake Redis blacklist for testing."""

    def __init__(self, revoked=None):
        self._revoked = revoked or set()

    async def is_revoked(self, *, jti: str) -> bool:
        return jti in self._revoked


async def test_gateway_confidence_store_is_injected():
    from src.service import GatewayService

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    fake_store = FakeConfidenceStore()

    service = GatewayService(jwt, confidence_store=fake_store)
    assert service._confidence_store is fake_store
    assert service._confidence_store is not None


async def test_valid_confidence_provenance():
    from src.service import GatewayService

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    confidence_id = str(uuid.uuid4())

    fake_store = FakeConfidenceStore(
        records={
            (TENANT_A, confidence_id): {
                "id": confidence_id,
                "tenant_id": TENANT_A,
                "target_type": "hypothesis",
                "target_id": str(uuid.uuid4()),
                "confidence_score": 0.85,
            }
        }
    )
    service = GatewayService(jwt, confidence_store=fake_store)

    result = await service.verify_confidence_provenance(
        tenant_id=TENANT_A,
        confidence_id=confidence_id,
        expected_target_type="hypothesis",
    )
    assert result is not None
    assert result["confidence_score"] == 0.85
    assert fake_store.get_called


async def test_missing_confidence_rejected():
    from src.boundary import ConfidenceProvenanceError
    from src.service import GatewayService

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    fake_store = FakeConfidenceStore(records={})
    service = GatewayService(jwt, confidence_store=fake_store)

    with pytest.raises(ConfidenceProvenanceError):
        await service.verify_confidence_provenance(
            tenant_id=TENANT_A,
            confidence_id=str(uuid.uuid4()),
            expected_target_type="hypothesis",
        )


async def test_unknown_confidence_rejected():
    from src.boundary import ConfidenceProvenanceError
    from src.service import GatewayService

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    fake_store = FakeConfidenceStore(records={})
    service = GatewayService(jwt, confidence_store=fake_store)

    with pytest.raises(ConfidenceProvenanceError):
        await service.verify_confidence_provenance(
            tenant_id=TENANT_A,
            confidence_id="nonexistent-id",
            expected_target_type="hypothesis",
        )


async def test_cross_tenant_confidence_rejected():
    from src.boundary import ConfidenceProvenanceError
    from src.service import GatewayService

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    confidence_id = str(uuid.uuid4())

    fake_store = FakeConfidenceStore(
        records={
            (TENANT_A, confidence_id): {
                "id": confidence_id,
                "tenant_id": TENANT_A,
                "target_type": "hypothesis",
                "target_id": str(uuid.uuid4()),
                "confidence_score": 0.85,
            }
        }
    )
    service = GatewayService(jwt, confidence_store=fake_store)

    with pytest.raises(ConfidenceProvenanceError):
        await service.verify_confidence_provenance(
            tenant_id=TENANT_B,
            confidence_id=confidence_id,
            expected_target_type="hypothesis",
        )


async def test_wrong_target_confidence_rejected():
    from src.boundary import ConfidenceProvenanceError
    from src.service import GatewayService

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    confidence_id = str(uuid.uuid4())

    fake_store = FakeConfidenceStore(
        records={
            (TENANT_A, confidence_id): {
                "id": confidence_id,
                "tenant_id": TENANT_A,
                "target_type": "hypothesis",
                "target_id": str(uuid.uuid4()),
                "confidence_score": 0.85,
            }
        }
    )
    service = GatewayService(jwt, confidence_store=fake_store)

    with pytest.raises(ConfidenceProvenanceError):
        await service.verify_confidence_provenance(
            tenant_id=TENANT_A,
            confidence_id=confidence_id,
            expected_target_type="recommendation",
        )


async def test_client_score_ignored():
    from src.service import GatewayService

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    confidence_id = str(uuid.uuid4())

    fake_store = FakeConfidenceStore(
        records={
            (TENANT_A, confidence_id): {
                "id": confidence_id,
                "tenant_id": TENANT_A,
                "target_type": "hypothesis",
                "target_id": str(uuid.uuid4()),
                "confidence_score": 0.85,
            }
        }
    )
    service = GatewayService(jwt, confidence_store=fake_store)

    result = await service.verify_confidence_provenance(
        tenant_id=TENANT_A,
        confidence_id=confidence_id,
        expected_target_type="hypothesis",
    )
    assert result["confidence_score"] == 0.85


async def test_confidence_store_unavailable_fails_closed():
    from src.service import GatewayService

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    service = GatewayService(jwt, confidence_store=None)

    with pytest.raises(SecurityControlUnavailable, match="confidence store not configured"):
        await service.verify_confidence_provenance(
            tenant_id=TENANT_A,
            confidence_id=str(uuid.uuid4()),
            expected_target_type="hypothesis",
        )


# ============================================================
# P1: JWT Revocation in middleware
# ============================================================


async def test_middleware_revocation_check():
    from libs.access.middleware import jwt_auth_middleware

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    token = jwt.create_access_token(
        user_id=str(uuid.uuid4()),
        tenant_id=TENANT_A,
        email="test@test.com",
        role="admin",
    )
    payload = jwt.verify_access_token(token)

    fake_blacklist = FakeBlacklist(revoked={payload.jti})

    middleware_fn = jwt_auth_middleware(jwt, blacklist=fake_blacklist)

    mock_request = MagicMock()
    mock_request.path = "/api/v1/reports"
    mock_request.headers = {"Authorization": f"Bearer {token}"}

    mock_handler = AsyncMock()

    with pytest.raises(InvalidTokenError, match="token has been revoked"):
        await middleware_fn(mock_request, mock_handler)


async def test_middleware_redis_unavailable_fails_closed():
    from libs.access.middleware import jwt_auth_middleware

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    token = jwt.create_access_token(
        user_id=str(uuid.uuid4()),
        tenant_id=TENANT_A,
        email="test@test.com",
        role="admin",
    )

    mock_blacklist = AsyncMock()
    mock_blacklist.is_revoked = AsyncMock(side_effect=SecurityControlUnavailable("Redis down"))

    middleware_fn = jwt_auth_middleware(jwt, blacklist=mock_blacklist)

    mock_request = MagicMock()
    mock_request.path = "/api/v1/reports"
    mock_request.headers = {"Authorization": f"Bearer {token}"}

    mock_handler = AsyncMock()

    with pytest.raises(InvalidTokenError, match="security control unavailable"):
        await middleware_fn(mock_request, mock_handler)


async def test_middleware_no_blacklist_skips_revocation():
    from libs.access.middleware import jwt_auth_middleware

    jwt = JwtService(algorithm="HS256", secret_key=SECRET)
    token = jwt.create_access_token(
        user_id=str(uuid.uuid4()),
        tenant_id=TENANT_A,
        email="test@test.com",
        role="admin",
    )

    middleware_fn = jwt_auth_middleware(jwt)

    mock_request = MagicMock()
    mock_request.path = "/api/v1/reports"
    mock_request.headers = {"Authorization": f"Bearer {token}"}

    mock_handler = AsyncMock(return_value=MagicMock(status=200))

    result = await middleware_fn(mock_request, mock_handler)
    assert result.status == 200
    assert mock_request["token"] is not None


# ============================================================
# Cookie Auth Tests
# ============================================================


def test_cookie_httponly():
    from aiohttp import web

    from libs.access.cookie_auth import set_refresh_cookie

    response = web.Response()
    set_refresh_cookie(response, "test-refresh-token")

    cookie = response.cookies.get("refresh_token")
    assert cookie is not None
    assert cookie["httponly"] is True


def test_cookie_secure():
    from aiohttp import web

    from libs.access.cookie_auth import set_refresh_cookie

    response = web.Response()
    set_refresh_cookie(response, "test-refresh-token")

    cookie = response.cookies.get("refresh_token")
    assert cookie is not None
    assert cookie["secure"] is True


def test_cookie_samesite():
    from aiohttp import web

    from libs.access.cookie_auth import set_refresh_cookie

    response = web.Response()
    set_refresh_cookie(response, "test-refresh-token")

    cookie = response.cookies.get("refresh_token")
    assert cookie is not None
    assert cookie["samesite"] == "Lax"


def test_cookie_path():
    from aiohttp import web

    from libs.access.cookie_auth import set_refresh_cookie

    response = web.Response()
    set_refresh_cookie(response, "test-refresh-token")

    cookie = response.cookies.get("refresh_token")
    assert cookie is not None
    assert cookie["path"] == "/api/v1/auth/refresh"


def test_clear_refresh_cookie():
    from aiohttp import web

    from libs.access.cookie_auth import clear_refresh_cookie

    response = web.Response()
    response.set_cookie("refresh_token", "test-token", path="/api/v1/auth/refresh")
    clear_refresh_cookie(response)

    cookie = response.cookies.get("refresh_token")
    assert cookie is not None
    # The cookie is marked for deletion (expires in the past)
    max_age = str(cookie.get("max-age", ""))
    expires = cookie.get("expires", "")
    assert max_age == "0" or expires.startswith("Thu, 01 Jan 1970")


def test_get_refresh_token_from_cookie():
    from libs.access.cookie_auth import get_refresh_token_from_cookie

    mock_request = MagicMock()
    mock_request.cookies = {"refresh_token": "test-refresh-token"}

    token = get_refresh_token_from_cookie(mock_request)
    assert token == "test-refresh-token"


def test_get_refresh_token_missing():
    from libs.access.cookie_auth import get_refresh_token_from_cookie

    mock_request = MagicMock()
    mock_request.cookies = {}

    token = get_refresh_token_from_cookie(mock_request)
    assert token is None


# ============================================================
# Production wiring verification (file content checks)
# ============================================================


def test_main_py_wires_confidence_store():
    main_path = _root / "apps" / "gateway" / "api-gateway" / "src" / "main.py"
    content = main_path.read_text()
    assert "confidence_store = ConfidenceReadStore(" in content
    assert "confidence_store=confidence_store," in content


def test_report_service_wires_blacklist():
    main_path = _root / "apps" / "services" / "report-service" / "src" / "main.py"
    content = main_path.read_text()
    assert "blacklist = TokenBlacklist.from_url(redis_url)" in content
    assert "jwt_auth_middleware(jwt, blacklist=blacklist)" in content


def test_frontend_no_localstorage_refresh():
    client_path = _root / "apps" / "web" / "src" / "api" / "client.ts"
    content = client_path.read_text()
    assert "localStorage.setItem(REFRESH_KEY" not in content
    assert "localStorage.getItem(REFRESH_KEY" not in content
    assert "export function getRefreshToken" not in content
    assert "credentials: 'include'" in content


def test_user_service_uses_cookie_auth():
    health_path = _root / "apps" / "services" / "user-service" / "src" / "health.py"
    content = health_path.read_text()
    assert "set_refresh_cookie" in content
    assert "get_refresh_token_from_cookie" in content
    assert "clear_refresh_cookie" in content


# ============================================================
# CSRF Protection Tests
# ============================================================


def test_csrf_middleware_wired_in_user_service():
    """Verify CSRF middleware is added to user service."""
    health_path = _root / "apps" / "services" / "user-service" / "src" / "health.py"
    content = health_path.read_text()
    assert "csrf_protection_middleware" in content


def test_csrf_rejects_mismatched_origin():
    """CSRF middleware rejects requests with mismatched Origin."""
    from libs.access.csrf import csrf_protection_middleware

    middleware_fn = csrf_protection_middleware()

    mock_request = MagicMock()
    mock_request.path = "/api/v1/auth/refresh"
    mock_request.headers = {
        "Origin": "https://evil.example.com",
        "Host": "localhost:8099",
    }

    mock_handler = AsyncMock()

    import asyncio

    from aiohttp import web

    with pytest.raises(web.HTTPForbidden):
        asyncio.run(middleware_fn(mock_request, mock_handler))


def test_csrf_allows_same_origin():
    """CSRF middleware allows requests with matching Origin."""
    from libs.access.csrf import csrf_protection_middleware

    middleware_fn = csrf_protection_middleware()

    mock_request = MagicMock()
    mock_request.path = "/api/v1/auth/refresh"
    mock_request.headers = {
        "Origin": "http://localhost:8099",
        "Host": "localhost:8099",
    }

    mock_handler = AsyncMock(return_value=MagicMock(status=200))

    import asyncio
    result = asyncio.run(middleware_fn(mock_request, mock_handler))
    assert result.status == 200


def test_csrf_allows_no_origin_header():
    """CSRF middleware allows requests without Origin (non-browser clients)."""
    from libs.access.csrf import csrf_protection_middleware

    middleware_fn = csrf_protection_middleware()

    mock_request = MagicMock()
    mock_request.path = "/api/v1/auth/refresh"
    mock_request.headers = {"Host": "localhost:8099"}

    mock_handler = AsyncMock(return_value=MagicMock(status=200))

    import asyncio
    result = asyncio.run(middleware_fn(mock_request, mock_handler))
    assert result.status == 200


def test_csrf_skips_non_protected_paths():
    """CSRF middleware skips validation on non-protected paths."""
    from libs.access.csrf import csrf_protection_middleware

    middleware_fn = csrf_protection_middleware()

    mock_request = MagicMock()
    mock_request.path = "/api/v1/auth/login"
    mock_request.headers = {"Origin": "https://evil.example.com"}

    mock_handler = AsyncMock(return_value=MagicMock(status=200))

    import asyncio
    result = asyncio.run(middleware_fn(mock_request, mock_handler))
    assert result.status == 200


def test_csrf_allows_extra_origins():
    """CSRF middleware allows configured extra origins."""
    from libs.access.csrf import csrf_protection_middleware

    middleware_fn = csrf_protection_middleware(
        allowed_origins=["http://localhost:5173"]
    )

    mock_request = MagicMock()
    mock_request.path = "/api/v1/auth/refresh"
    mock_request.headers = {
        "Origin": "http://localhost:5173",
        "Host": "localhost:8099",
    }

    mock_handler = AsyncMock(return_value=MagicMock(status=200))

    import asyncio
    result = asyncio.run(middleware_fn(mock_request, mock_handler))
    assert result.status == 200


def test_csrf_uses_referer_fallback():
    """CSRF middleware falls back to Referer when Origin is missing."""
    from libs.access.csrf import _get_origin

    mock_request = MagicMock()
    mock_request.headers = {
        "Referer": "http://localhost:8099/some-page",
    }
    origin = _get_origin(mock_request)
    assert origin == "http://localhost:8099"
