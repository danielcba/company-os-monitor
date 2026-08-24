"""HTTP surface for the User Service: /health, /metrics, auth + users API.

External non-canonical capability (ADR-0002): the endpoints only authenticate
and authorize - they never produce cognitive judgments. Endpoints:

- ``POST /api/v1/auth/login``        email+password -> access+refresh tokens
- ``POST /api/v1/auth/refresh``      refresh token -> new access+refresh pair (rotation)
- ``POST /api/v1/auth/logout``       blacklists the refresh token
- ``POST /api/v1/users``             create a user in the actor's tenant
- ``GET  /api/v1/me``                profile + role of the authenticated user
- ``GET  /api/v1/users``             list users of the actor's tenant

All user endpoints are tenant-isolated: a user only sees its own tenant
(multi-tenant); cross-tenant access requires superadmin authority.
"""
import logging
import os
import uuid

from aiohttp import web
from aiohttp_cors import ResourceOptions, setup as cors_setup

from libs.access.errors import (
    AccessError,
    InvalidTokenError,
    UserConflictError,
)
from libs.access.security import JwtService, TokenPayload
from libs.access.token_blacklist import TokenBlacklist

from src.service import AuthService
from src.ratelimit import RateLimiter, RateLimiterUnavailable

logger = logging.getLogger(__name__)


class UserServer:
    def __init__(self, service: AuthService, jwt: JwtService):
        self.service = service
        self.jwt = jwt
        self._rate_limiter = RateLimiter.from_url(
            os.getenv("JWT_REDIS_URL", "redis://localhost:6379/1")
        )
        self.app = web.Application()
        self._setup_cors()
        # Add security headers middleware.
        from libs.shared.security_headers import security_headers_middleware
        self.app.middlewares.append(security_headers_middleware())
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.app.router.add_post("/api/v1/auth/login", self.login_handler)
        self.app.router.add_post("/api/v1/auth/refresh", self.refresh_handler)
        self.app.router.add_post("/api/v1/auth/logout", self.logout_handler)
        self.app.router.add_post("/api/v1/users", self.create_user_handler)
        self.app.router.add_get("/api/v1/me", self.me_handler)
        self.app.router.add_get("/api/v1/users", self.list_users_handler)
        self.app.router.add_get("/api/v1/tenants", self.list_tenants_handler)
        self.app.router.add_get("/api/v1/tenants/{tenant_id}", self.get_tenant_handler)
        self.app.router.add_put("/api/v1/users/{user_id}", self.update_user_handler)
        self.app.router.add_delete("/api/v1/users/{user_id}", self.deactivate_user_handler)
        self.runner = None

    def _setup_cors(self) -> None:
        allowed_origins = [
            o.strip()
            for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        cors = cors_setup(
            self.app,
            defaults={
                origin: ResourceOptions(
                    allow_credentials=True,
                    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                    allow_headers=["Authorization", "Content-Type"],
                    expose_headers=["Authorization"],
                )
                for origin in allowed_origins
            },
        )
        for route in self.app.router.routes():
            cors.add(route)

    async def start(self, port: int = 8099):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    async def stop(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.service.total_errors == 0 else "degraded",
            "logins": self.service.total_logins,
            "login_failures": self.service.total_login_failures,
            "errors": self.service.total_errors,
            "last_login_at": (
                self.service.last_login_at.isoformat()
                if self.service.last_login_at
                else None
            ),
        })

    async def metrics_handler(self, request):
        return web.json_response(self.service.metrics())

    async def login_handler(self, request):
        client_ip = request.remote or "unknown"
        try:
            if not await self._rate_limiter.is_allowed(f"login:{client_ip}"):
                return web.json_response(
                    {"error": "Too many requests, try again later"},
                    status=429,
                )
        except RateLimiterUnavailable:
            return web.json_response(
                {"error": "Rate limiter unavailable; request rejected (fail-closed)"},
                status=429,
            )
        try:
            body = await request.json()
            result = await self.service.login(
                email=str(body.get("email", "")),
                password=str(body.get("password", "")),
                tenant_id=body.get("tenant_id"),
            )
            return web.json_response(result, status=200)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def refresh_handler(self, request):
        client_ip = request.remote or "unknown"
        try:
            if not await self._rate_limiter.is_allowed(f"refresh:{client_ip}"):
                return web.json_response(
                    {"error": "Too many requests, try again later"},
                    status=429,
                )
        except RateLimiterUnavailable:
            return web.json_response(
                {"error": "Rate limiter unavailable; request rejected (fail-closed)"},
                status=429,
            )
        try:
            body = await request.json()
            result = await self.service.refresh(
                refresh_token=str(body.get("refresh_token", ""))
            )
            return web.json_response(result, status=200)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def logout_handler(self, request):
        """Blacklist the refresh token to revoke access immediately."""
        try:
            body = await request.json()
            await self.service.logout(
                refresh_token=str(body.get("refresh_token", ""))
            )
            return web.json_response({"status": "logged out"}, status=200)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def create_user_handler(self, request):
        try:
            actor = self._authenticate(request)
            body = await request.json()
            user = await self.service.create_user(
                actor=actor,
                email=str(body.get("email", "")),
                password=str(body.get("password", "")),
                name=body.get("name"),
                role=str(body.get("role", "viewer")),
                tenant_id=body.get("tenant_id"),
            )
            return web.json_response(_user_payload(user), status=201)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except UserConflictError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            logger.exception("Error in create_user_handler")
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def me_handler(self, request):
        try:
            actor = self._authenticate(request)
            user = await self.service.user_store.get_by_id(
                id=uuid.UUID(actor.user_id)
            )
            if user is None:
                return web.json_response({"error": "unknown user"}, status=401)
            return web.json_response(_user_payload(user))
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            logger.exception("Error in me_handler")
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def list_users_handler(self, request):
        try:
            actor = self._authenticate(request)
            users = await self.service.list_users(
                actor=actor, tenant_id=request.query.get("tenant_id")
            )
            return web.json_response({"users": [_user_payload(u) for u in users]})
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            logger.exception("Error in list_users_handler")
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def list_tenants_handler(self, request):
        try:
            actor = self._authenticate(request)
            tenants = await self.service.list_tenants(actor=actor)
            return web.json_response({"tenants": [_tenant_payload(t) for t in tenants]})
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            logger.exception("Error in list_tenants_handler")
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def get_tenant_handler(self, request):
        try:
            actor = self._authenticate(request)
            tenant_id = request.match_info["tenant_id"]
            tenant = await self.service.get_tenant(actor=actor, tenant_id=tenant_id)
            if tenant is None:
                return web.json_response({"error": "tenant not found"}, status=404)
            return web.json_response(_tenant_payload(tenant))
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            logger.exception("Error in get_tenant_handler")
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def update_user_handler(self, request):
        try:
            actor = self._authenticate(request)
            user_id = request.match_info["user_id"]
            body = await request.json()
            user = await self.service.update_user(
                actor=actor,
                user_id=user_id,
                name=body.get("name"),
                role=body.get("role"),
            )
            return web.json_response(_user_payload(user))
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            logger.exception("Error in update_user_handler")
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def deactivate_user_handler(self, request):
        try:
            actor = self._authenticate(request)
            user_id = request.match_info["user_id"]
            user = await self.service.deactivate_user(actor=actor, user_id=user_id)
            return web.json_response(_user_payload(user))
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            logger.exception("Error in deactivate_user_handler")
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    def _authenticate(self, request) -> TokenPayload:
        """Verify the Bearer token -> identity + authority + tenant claims."""
        header = request.headers.get("Authorization", "")
        if not header.lower().startswith("bearer "):
            raise InvalidTokenError("missing bearer token")
        token = header.split(" ", 1)[1].strip()
        return self.jwt.verify_access_token(token)


def _user_payload(user) -> dict[str, Any]:
    """Public view of a user: identity + role, NEVER the password hash."""
    return {
        "id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def _tenant_payload(tenant) -> dict[str, Any]:
    """Public view of a tenant."""
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "settings": tenant.settings,
        "created_at": tenant.created_at.isoformat(),
        "updated_at": tenant.updated_at.isoformat(),
    }
