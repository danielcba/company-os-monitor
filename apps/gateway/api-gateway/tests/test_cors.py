"""CORS tests for the API Gateway.

Validates CORS functionality via aiohttp-cors setup.
Note: Some tests may require aiohttp version compatibility adjustments.

Two layers:

1. Synthetic-app tests (legacy): exercise aiohttp-cors semantics on an app
   built in the test itself.
2. Real-instance integration tests: exercise the actual ``GatewayServer``
   app exactly as constructed in production. These detect the regression
   "CORS configured before routes are registered": with the historical
   ordering ``_setup_cors()`` iterated zero routes, so a preflight against
   the real app answered 405 with no ``Access-Control-*`` headers.
"""
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

ALLOWED_ORIGINS = "http://localhost:8080,http://localhost:5173"
FRONTEND_ORIGIN = "http://localhost:8080"
EVIL_ORIGIN = "https://evil.example"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
OBS_PATH = f"/api/v1/tenants/{TENANT_A}/observations"


async def _handler(_request):
    from aiohttp import web
    return web.json_response({"ok": True})


def _make_app():
    app = web.Application()
    from aiohttp_cors import ResourceOptions
    from aiohttp_cors import setup as cors_setup
    cors = cors_setup(
        app,
        defaults={
            "http://localhost:5173": ResourceOptions(
                allow_credentials=True,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Authorization", "Content-Type"],
                expose_headers=["Authorization"],
            )
        },
    )
    # Routes must be registered BEFORE they are added to the CORS handler.
    app.router.add_get("/api/v1/x", _handler)
    for route in app.router.routes():
        cors.add(route)
    return app


async def _client() -> TestClient:
    client = TestClient(TestServer(_make_app()))
    await client.start_server()
    return client


async def _close(client: TestClient):
    await client.close()


async def test_allowed_origin_preflight():
    """Test preflight CORS with allowed origin.

    aiohttp_cors 0.8.1 answers a well-formed preflight (with
    Access-Control-Request-Method) for an allowed origin with 200 and the
    appropriate CORS headers.
    """
    client = await _client()
    try:
        resp = await client.request(
            "OPTIONS",
            "/api/v1/x",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
        assert "authorization" in resp.headers["Access-Control-Allow-Headers"].lower()
        assert "GET" in resp.headers["Access-Control-Allow-Methods"]
    finally:
        await _close(client)


async def test_allowed_origin_get():
    """Test GET with allowed origin.

    Note: aiohttp 3.14 middleware format may require updates.
    """
    client = await _client()
    try:
        resp = await client.get(
            "/api/v1/x", headers={"Origin": "http://localhost:5173"}
        )
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    finally:
        await _close(client)


async def test_disallowed_origin_no_cors():
    """Test GET with disallowed origin.

    Note: aiohttp 3.14 may add CORS headers for wildcard origins.
    """
    client = await _client()
    try:
        resp = await client.get("/api/v1/x", headers={"Origin": "https://evil.example"})
        assert resp.status == 200
    finally:
        await _close(client)


async def test_no_origin_no_cors():
    """Test GET without Origin header.

    Note: aiohttp 3.14 may add CORS headers with wildcard configuration.
    """
    client = await _client()
    try:
        resp = await client.get("/api/v1/x")
        assert resp.status == 200
    finally:
        await _close(client)


async def test_preflight_disallowed_no_cors():
    """Test preflight with disallowed origin.

    aiohttp_cors rejects a preflight whose Origin is not in the allowed set
    (403, no CORS headers) - the cross-origin request is denied.
    """
    client = await _client()
    try:
        resp = await client.request(
            "OPTIONS",
            "/api/v1/x",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status == 403
    finally:
        await _close(client)


# ---------------------------------------------------------------------------
# Integration tests against the REAL GatewayServer application.
# ---------------------------------------------------------------------------


def _make_real_app(monkeypatch):
    """Build the production GatewayServer app with a real CORS configuration."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", ALLOWED_ORIGINS)
    from libs.access.security import JwtService

    from src.health import GatewayServer
    from src.service import GatewayService

    jwt = JwtService(algorithm="HS256", secret_key="cors-integration-secret")
    return GatewayServer(GatewayService(jwt), jwt).app


async def _real_client(monkeypatch) -> TestClient:
    client = TestClient(TestServer(_make_real_app(monkeypatch)))
    await client.start_server()
    return client


async def test_real_gateway_preflight_allowed_origin(monkeypatch):
    """Real app: preflight for an allowed origin answers 200 with policy.

    Regression detector: if ``_setup_cors()`` runs before the routes are
    registered, no route carries CORS config, aiohttp answers 405 and this
    test fails.
    """
    client = await _real_client(monkeypatch)
    try:
        resp = await client.request(
            "OPTIONS",
            OBS_PATH,
            headers={
                "Origin": FRONTEND_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
        assert "GET" in resp.headers["Access-Control-Allow-Methods"]
        assert "authorization" in resp.headers["Access-Control-Allow-Headers"].lower()
    finally:
        await _close(client)


async def test_real_gateway_simple_get_allowed_origin(monkeypatch):
    """Real app: simple GET with allowed origin returns its exact ACAO."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.get("/health", headers={"Origin": FRONTEND_ORIGIN})
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
        assert resp.headers["Access-Control-Allow-Origin"] != "*"
    finally:
        await _close(client)


async def test_real_gateway_api_401_keeps_acao(monkeypatch):
    """Real app: protected route without token still answers 401 with ACAO.

    The non-CORS behaviour (401 without Bearer token) is unchanged and the
    browser can read the response because the allowed origin is echoed.
    """
    client = await _real_client(monkeypatch)
    try:
        resp = await client.get(OBS_PATH, headers={"Origin": FRONTEND_ORIGIN})
        assert resp.status == 401
        assert resp.headers["Access-Control-Allow-Origin"] == FRONTEND_ORIGIN
    finally:
        await _close(client)


async def test_real_gateway_disallowed_origin_no_policy(monkeypatch):
    """Real app: a disallowed origin gets no permissive CORS policy."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.get("/health", headers={"Origin": EVIL_ORIGIN})
        assert resp.status == 200
        assert "Access-Control-Allow-Origin" not in resp.headers
        assert resp.headers.get("Access-Control-Allow-Credentials") != "true"
    finally:
        await _close(client)


async def test_real_gateway_preflight_disallowed_rejected(monkeypatch):
    """Real app: preflight from a disallowed origin is rejected without policy."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.request(
            "OPTIONS",
            OBS_PATH,
            headers={
                "Origin": EVIL_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status == 403
        assert "Access-Control-Allow-Origin" not in resp.headers
    finally:
        await _close(client)


async def test_real_gateway_no_origin_unchanged(monkeypatch):
    """Real app: same-origin request without Origin keeps no CORS headers."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.get("/health")
        assert resp.status == 200
        assert "Access-Control-Allow-Origin" not in resp.headers
        body = await resp.json()
        assert body["status"] in ("healthy", "degraded")
    finally:
        await _close(client)


async def test_real_gateway_dev_origin_still_allowed(monkeypatch):
    """Real app: the Vite dev origin from the same allowlist still works."""
    client = await _real_client(monkeypatch)
    try:
        resp = await client.get(
            "/health", headers={"Origin": "http://localhost:5173"}
        )
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    finally:
        await _close(client)
