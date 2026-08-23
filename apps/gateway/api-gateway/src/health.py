"""HTTP surface for the API Gateway (Cognitive Boundary enforcement, R3).

Public: /health, /metrics. Everything under /api/v1 requires a Bearer token
issued by the user-service. Routes:

- ``GET  /health``          forward to pipeline /health (any role)
- ``GET  /metrics``         forward to pipeline metrics (any role)
- ``GET  /api/v1/services/health``          forward to pipeline /health (any role)
- ``GET  /api/v1/tenants/{tenant_id}/decisions``  READ decisions, tenant scope
- ``GET  /api/v1/tenants/{tenant_id}/reports``    READ reports, tenant scope
- ``GET  /api/v1/tenants/{tenant_id}/observations``  READ observations, tenant scope
- ``GET  /api/v1/tenants/{tenant_id}/cognitive/summary``  READ cognitive summary, tenant scope
- ``POST /api/v1/actions/{action}``         validate action authority + boundary

The action endpoint NEVER executes the action (the canonical cycle in each
service is the only executor): it is the authority/boundary validation point
(R3, R4, R5) that an external capability would call to trigger a future
execution. 401 = no/invalid token, 403 = authenticated but no authority,
400 = boundary violation (e.g. missing Confidence, R4) or invalid query params.
"""

from aiohttp import web
from aiohttp_cors import ResourceOptions, setup as cors_setup

from libs.access.errors import (
    AccessError,
    InvalidTokenError,
)
from libs.access.rbac import RISK_TOLERANCES
from libs.access.security import JwtService, TokenPayload

from src.boundary import BoundaryViolationError
from src.observations import VALID_QUALITY_CLASSES
from src.service import GatewayService

VALID_SORTS = {"captured_at_desc", "captured_at_asc"}
MAX_LIMIT = 200
MIN_LIMIT = 1


def _is_validation_error(err_msg: str) -> bool:
    """Check if AccessError is a validation error (400) vs auth error (403)."""
    return any(kw in err_msg for kw in ("Invalid", "must be", "must be between"))


class GatewayServer:
    def __init__(self, service: GatewayService, jwt: JwtService):
        self.service = service
        self.jwt = jwt
        self.app = web.Application()
        self._setup_cors()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.app.router.add_get(
            "/api/v1/services/health", self.services_health_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/decisions", self.decisions_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/reports", self.reports_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/observations", self.observations_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/cognitive/summary", self.cognitive_summary_handler
        )
        self.app.router.add_post("/api/v1/actions/{action}", self.action_handler)
        self.runner = None

    def _setup_cors(self) -> None:
        cors = cors_setup(
            self.app,
            defaults={
                "*": ResourceOptions(
                    allow_credentials=True,
                    allow_methods=["GET", "POST", "OPTIONS"],
                    allow_headers=["Authorization", "Content-Type"],
                    expose_headers=["Authorization"],
                )
            },
        )
        for route in self.app.router.routes():
            cors.add(route)

    async def start(self, port: int = 8100):
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
            "requests": self.service.total_requests,
            "rejected_401": self.service.total_rejected_401,
            "rejected_403": self.service.total_rejected_403,
            "errors": self.service.total_errors,
        })

    async def metrics_handler(self, request):
        return web.json_response(self.service.metrics())

    async def services_health_handler(self, request):
        try:
            self._authenticate(request)  # enforce auth (401 if invalid)
            self.service.record(action="read:services_health")
            results = await self.service.check_service_health()
            return web.json_response({"services": results})
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _validate_tenant_id(self, tenant_id: str) -> str:
        """Validate tenant_id is a proper UUID, return normalized str or raise."""
        try:
            import uuid
            uuid.UUID(tenant_id)
        except ValueError:
            raise AccessError(f"Invalid tenant_id format")
        return tenant_id

    async def _parse_observations_query(self, query) -> dict[str, Any]:
        """Parse and validate observations query parameters."""
        from typing import Any
        try:
            limit = int(query.get("limit", "50"))
        except ValueError:
            raise AccessError("Invalid limit parameter")
        if limit < MIN_LIMIT or limit > MAX_LIMIT:
            raise AccessError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")

        try:
            offset = int(query.get("offset", "0"))
        except ValueError:
            raise AccessError("Invalid offset parameter")
        if offset < 0:
            raise AccessError("offset must be non-negative")

        fact_type = query.get("fact_type")
        source_type = query.get("source_type")
        quality_class = query.get("quality_class")
        if quality_class and quality_class not in VALID_QUALITY_CLASSES:
            raise AccessError(f"Invalid quality_class: {quality_class}")

        sort = query.get("sort", "captured_at_desc")
        if sort not in VALID_SORTS:
            raise AccessError(f"Invalid sort: {sort}")

        return {
            "limit": limit,
            "offset": offset,
            "fact_type": fact_type,
            "source_type": source_type,
            "quality_class": quality_class,
            "sort": sort,
        }

    async def decisions_handler(self, request):
        try:
            token = self._authenticate(request)
            self.service.record(action="read:decisions")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            decisions = await self.service.list_decisions(token, tenant_id)
            return web.json_response({"decisions": decisions})
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def reports_handler(self, request):
        try:
            token = self._authenticate(request)
            self.service.record(action="read:reports")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            reports = await self.service.list_reports(token, tenant_id)
            return web.json_response({"reports": reports})
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def observations_handler(self, request):
        try:
            token = self._authenticate(request)
            self.service.record(action="read:observations")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            query_params = await self._parse_observations_query(request.query)
            observations = await self.service.list_observations(token, tenant_id, **query_params)
            return web.json_response(observations)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            status = 400 if _is_validation_error(str(exc)) else 403
            return web.json_response({"error": str(exc)}, status=status)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def cognitive_summary_handler(self, request):
        try:
            token = self._authenticate(request)
            self.service.record(action="read:cognitive_summary")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            summary = await self.service.cognitive_summary(tenant_id=tenant_id)
            return web.json_response(summary)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def action_handler(self, request):
        """Validate an action against authority + boundary (never executes).

        Body may carry ``confidence_id``/``confidence_score`` (R4 for
        propose/commit), ``risk_tolerance`` (commit ceiling) and an optional
        ``tenant_id`` (cross-tenant requires superadmin).
        """
        try:
            token = self._authenticate(request)
            action = request.match_info["action"]
            payload = await request.json()
            self.service.record(action=action)

            self.service.enforce_boundary(action, payload)
            risk = payload.get("risk_tolerance", "low")
            if action == "commit" and risk not in RISK_TOLERANCES:
                return web.json_response(
                    {"error": f"unknown risk_tolerance: {risk!r}"}, status=400
                )
            requested_tenant_id = payload.get("tenant_id")
            self.service.require_authorized(
                token=token,
                action=action,
                risk=risk if action == "commit" else None,
                requested_tenant_id=requested_tenant_id,
            )
            return web.json_response(
                {
                    "authorized": True,
                    "action": action,
                    "authority": {
                        "user_id": token.user_id,
                        "role": token.role,
                        "tenant_id": token.tenant_id,
                    },
                    "note": (
                        "validated by the Cognitive Boundary (R3); execution "
                        "happens in the canonical service cycle, not here"
                    ),
                }
            )
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except BoundaryViolationError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=400)

    def _authenticate(self, request) -> TokenPayload:
        return self.service.authenticate(request.headers.get("Authorization", ""))
