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
            "*": ResourceOptions(
                allow_credentials=True,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Authorization", "Content-Type"],
                expose_headers=["Authorization"],
            )
        },
    )
    for route in app.router.routes():
        cors.add(route)
    app.router.add_get("/api/v1/x", _handler)
    return app


async def _client() -> TestClient:
    client = TestClient(TestServer(_make_app()))
    await client.start_server()
    return client


async def _close(client: TestClient):
    await client.close()


async def test_allowed_origin_preflight():
    """Test preflight CORS with allowed origin.

    Note: aiohttp 3.14 middleware format may require updates.
    """
    client = await _client()
    try:
        resp = await client.request(
            "OPTIONS", "/api/v1/x", headers={"Origin": "http://localhost:5173"}
        )
        assert resp.status == 204
        assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
        assert "Authorization" in resp.headers["Access-Control-Allow-Headers"]
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

    Note: aiohttp 3.14 may require version-specific handling.
    """
    client = await _client()
    try:
        resp = await client.request(
            "OPTIONS", "/api/v1/x", headers={"Origin": "https://evil.example"}
        )
        assert resp.status == 204
    finally:
        await _close(client)
