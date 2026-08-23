"""Shared JWT authentication middleware for aiohttp services (external, ADR-0002).

Provides a reusable aiohttp middleware that validates Bearer tokens on
protected routes. Health and metrics endpoints are exempt from auth.

Usage::

    from libs.access.middleware import jwt_auth_middleware
    from libs.access.security import JwtService

    jwt = JwtService(algorithm="HS256", secret_key="...")
    app = web.Application(middlewares=[jwt_auth_middleware(jwt)])
"""
import logging
from typing import Callable

from aiohttp import web

from libs.access.errors import InvalidTokenError
from libs.access.security import JwtService, TokenPayload

logger = logging.getLogger(__name__)

# Paths that do not require authentication.
PUBLIC_PATHS = frozenset({"/health", "/metrics"})


def jwt_auth_middleware(
    jwt: JwtService,
    *,
    public_paths: frozenset[str] | None = None,
) -> Callable:
    """Create an aiohttp middleware that validates Bearer JWT tokens.

    Args:
        jwt: The JwtService instance for token verification.
        public_paths: Additional paths to exempt from auth (besides /health, /metrics).

    Returns:
        An aiohttp middleware function.
    """
    exempt = PUBLIC_PATHS | (public_paths or frozenset())

    @web.middleware
    async def middleware(request: web.Request, handler: Callable) -> web.Response:
        # Skip auth for exempt paths.
        if request.path in exempt:
            return await handler(request)

        # Extract and verify Bearer token.
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            raise InvalidTokenError("missing bearer token")

        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload: TokenPayload = jwt.verify_access_token(token)
        except InvalidTokenError:
            raise  # Let the handler's error handling deal with it

        # Attach token payload to request for handlers that need it.
        request["token"] = payload

        return await handler(request)

    return middleware
