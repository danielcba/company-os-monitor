"""HTTP surface for the User Service: /health, /metrics, auth + users API.

External non-canonical capability (ADR-0002): the endpoints only authenticate
and authorize - they never produce cognitive judgments. Endpoints:

- ``POST /api/v1/auth/login``        email+password -> access+refresh tokens
- ``POST /api/v1/auth/refresh``      refresh token -> new access token
- ``POST /api/v1/users``             create a user in the actor's tenant
- ``GET  /api/v1/me``                profile + role of the authenticated user
- ``GET  /api/v1/users``             list users of the actor's tenant

All user endpoints are tenant-isolated: a user only sees its own tenant
(multi-tenant); cross-tenant access requires superadmin authority.
"""
import uuid
from typing import Any

from aiohttp import web
from libs.access.errors import (
    AccessError,
    InvalidTokenError,
    UserConflictError,
)
from libs.access.security import JwtService, TokenPayload

from src.service import AuthService


class UserServer:
    def __init__(self, service: AuthService, jwt: JwtService):
        self.service = service
        self.jwt = jwt
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.app.router.add_post("/api/v1/auth/login", self.login_handler)
        self.app.router.add_post("/api/v1/auth/refresh", self.refresh_handler)
        self.app.router.add_post("/api/v1/users", self.create_user_handler)
        self.app.router.add_get("/api/v1/me", self.me_handler)
        self.app.router.add_get("/api/v1/users", self.list_users_handler)
        self.runner = None

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
            return web.json_response({"error": str(exc)}, status=400)

    async def refresh_handler(self, request):
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
            return web.json_response({"error": str(exc)}, status=400)

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
            self.service.total_errors += 1
            return web.json_response({"error": str(exc)}, status=400)

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
            self.service.total_errors += 1
            return web.json_response({"error": str(exc)}, status=400)

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
            self.service.total_errors += 1
            return web.json_response({"error": str(exc)}, status=400)

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