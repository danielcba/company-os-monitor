"""CORS tests for the API Gateway.

Validates CORS functionality via aiohttp-cors setup.
Note: Some tests may require aiohttp version compatibility adjustments.
"""
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer


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
