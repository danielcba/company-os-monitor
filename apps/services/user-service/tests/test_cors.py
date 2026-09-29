"""CORS integration tests against the REAL UserServer application.

The historical regression configured CORS before the routes were registered,
so ``self.app.router.routes()`` was empty, no ``Access-Control-*`` header was
ever emitted, and the browser could not call login cross-origin. These tests
instantiate the production ``UserServer`` exactly as ``src.main`` does and
exercise preflight, real login and simple requests against that app.
"""
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiohttp.test_utils import TestClient, TestServer
from libs.access.security import JwtService, hash_password
from libs.access.users import User

from src.health import UserServer
from src.ratelimit import RateLimiter
from src.service import AuthService

SECRET = "cors-integration-secret"
ALLOWED_ORIGINS = "http://localhost:8080,http://localhost:5173"
FRONTEND_ORIGIN = "http://localhost:8080"
DEV_ORIGIN = "http://localhost:5173"
EVIL_ORIGIN = "https://evil.example"
TENANT_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
USER_EMAIL = "cors-login@x.test"
USER_PASSWORD = "cors-login-pass-1"


class _Store:
    """Minimal in-memory user store (login path only)."""

    def __init__(self):
        self._by_email: dict[str, User] = {}

    async def create_user(self, *, tenant_id, email, password_hash, name, role,
                          is_active=True):
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            name=name,
            role=role,
            is_active=is_active,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._by_email[email] = user
        return user

    async def get_by_email(self, *, email):
        return self._by_email.get(email)


async def _seed(store: _Store) -> None:
    await store.create_user(
        tenant_id=TENANT_A,
        email=USER_EMAIL,
        password_hash=hash_password(USER_PASSWORD),
        name="cors login",
        role="viewer",
        is_active=True,
    )


async def _real_client(monkeypatch) -> TestClient:
    """Real UserServer (same construction as production src.main)."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", ALLOWED_ORIGINS)
    jwt = JwtService(
        algorithm="HS256",
        secret_key=SECRET,
        access_expire_minutes=15,
        refresh_expire_days=7,
    )
    store = _Store()
    await _seed(store)
    server = UserServer(AuthService(store, jwt), jwt)
    server._rate_limiter = RateLimiter(max_requests=999999, window_seconds=1, redis=None)
    client = TestClient(TestServer(server.app))
    await client.start_server()
    return client


async def test_real_user_preflight_login_allowed_origin(monkeypatch):
    """Real app: login preflight from the published frontend origin.

    Regression detector: with CORS configured before route registration this
    preflight answers 405 without CORS headers instead of 200.
    """
    client = await _real_client(monkeypatch)
    try:
        resp = await client.request(
            "OPTIONS",
            "/api/v1/auth/login",
            headers={
                "Origin": FRONTEND_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
        assert "POST" in resp.headers["Access-Control-Allow-Methods"]
        assert "content-type" in resp.headers["Access-Control-Allow-Headers"].lower()
    finally:
        await client.close()


async def test_real_user_login_allowed_origin(monkeypatch):
    """Real app: a successful cross-origin login is readable by the browser."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": USER_EMAIL, "password": USER_PASSWORD},
            headers={"Origin": FRONTEND_ORIGIN},
        )
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
        body = await resp.json()
        assert body["access_token"]
        assert body["token_type"]
    finally:
        await client.close()


async def test_real_user_login_invalid_credentials_keeps_acao(monkeypatch):
    """Real app: 401 from login keeps the allowed-origin policy (readable)."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": USER_EMAIL, "password": "wrong-password"},
            headers={"Origin": FRONTEND_ORIGIN},
        )
        assert resp.status == 401
        assert resp.headers["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
    finally:
        await client.close()


async def test_real_user_health_get_allowed_origin(monkeypatch):
    """Real app: simple GET with allowed origin returns its exact ACAO."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.get("/health", headers={"Origin": FRONTEND_ORIGIN})
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
        assert resp.headers["Access-Control-Allow-Origin"] != "*"
    finally:
        await client.close()


async def test_real_user_disallowed_origin_no_policy(monkeypatch):
    """Real app: a disallowed origin gets no permissive CORS policy."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.get("/health", headers={"Origin": EVIL_ORIGIN})
        assert resp.status == 200
        assert "Access-Control-Allow-Origin" not in resp.headers
        assert resp.headers.get("Access-Control-Allow-Credentials") != "true"

        resp_preflight = await client.request(
            "OPTIONS",
            "/api/v1/auth/login",
            headers={
                "Origin": EVIL_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp_preflight.status == 403
        assert "Access-Control-Allow-Origin" not in resp_preflight.headers
    finally:
        await client.close()


async def test_real_user_no_origin_unchanged(monkeypatch):
    """Real app: request without Origin keeps no CORS headers (non-CORS path)."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.get("/health")
        assert resp.status == 200
        assert "Access-Control-Allow-Origin" not in resp.headers
    finally:
        await client.close()


async def test_real_user_dev_origin_still_allowed(monkeypatch):
    """Real app: the Vite dev origin from the same allowlist still works."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.get("/health", headers={"Origin": DEV_ORIGIN})
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == DEV_ORIGIN
    finally:
        await client.close()
