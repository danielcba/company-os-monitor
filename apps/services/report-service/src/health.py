"""HTTP surface for the Report service: /health, /metrics, /api/v1/reports.

The Report service is non-canonical (ADR-0002): it exposes the report
generate/list endpoints plus operational metrics (no rule numbers). The
generate endpoint accepts ``type`` (executive/technical/json) and an optional
``tenant_id``; without a tenant it generates for the requesting user's tenant.

Protected endpoints require a valid Bearer JWT token (enforced by the
jwt_auth_middleware from libs.access.middleware).

Phase 20: Tenant isolation — the generate and list endpoints enforce that
the requesting user may only access their own tenant (cross-tenant requires
superadmin authority). No implicit all-tenants generation.
"""
import uuid
from typing import Any

from aiohttp import web

from libs.access.errors import AccessError, InvalidTokenError
from libs.access.rbac import cross_tenant_allowed
from libs.access.security import JwtService, TokenPayload
from libs.access.tenant_scope import AuthorizationContext, TenantScopeError

from src.service import RENDERABLE_TYPES, ReportService


class ReportServer:
    def __init__(self, service: ReportService, jwt: JwtService | None = None):
        self.service = service
        self.jwt = jwt
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.app.router.add_post("/api/v1/reports/generate", self.generate_handler)
        self.app.router.add_get("/api/v1/reports", self.list_handler)
        self.runner = None

    async def start(self, port: int = 8098):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    async def stop(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()

    async def _authenticate(self, request) -> TokenPayload:
        """Verify the Bearer token -> identity + authority + tenant claims."""
        if self.jwt is None:
            raise InvalidTokenError("JWT service not configured")
        header = request.headers.get("Authorization", "")
        if not header.lower().startswith("bearer "):
            raise InvalidTokenError("missing bearer token")
        token = header.split(" ", 1)[1].strip()
        return self.jwt.verify_access_token(token)

    async def _resolve_tenant(
        self, token: TokenPayload, requested_tenant_id: str | None
    ) -> str:
        """Resolve effective tenant from token + request (tenant isolation).

        If no tenant_id is requested, uses the token's own tenant.
        Cross-tenant requires superadmin authority.
        """
        effective = token.tenant_id
        if requested_tenant_id and str(requested_tenant_id) != token.tenant_id:
            if not cross_tenant_allowed(token.role):
                raise AccessError(
                    "cross-tenant report access requires superadmin authority"
                )
            effective = requested_tenant_id
        return effective

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.service.total_errors == 0 else "degraded",
            "reports": self.service.total_reports,
            "duplicates": self.service.total_report_duplicates,
            "errors": self.service.total_errors,
            "last_run_at": (
                self.service.last_run_at.isoformat()
                if self.service.last_run_at
                else None
            ),
        })

    async def metrics_handler(self, request):
        return web.json_response(self.service.metrics())

    async def generate_handler(self, request):
        report_type = request.query.get("type", "executive")
        if report_type not in RENDERABLE_TYPES:
            return web.json_response(
                {"error": f"unsupported report type: {report_type}"}, status=400
            )
        try:
            token = await self._authenticate(request)
            tenant_raw = request.query.get("tenant_id")
            effective_tenant = await self._resolve_tenant(token, tenant_raw)
            report, status = await self.service.generate(
                uuid.UUID(effective_tenant), report_type
            )
            return web.json_response(
                {"generated": [_report_payload(report, status)]}
            )
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            return web.json_response({"error": "Internal server error"}, status=500)

    async def list_handler(self, request):
        try:
            token = await self._authenticate(request)
            tenant_raw = request.query.get("tenant_id")
            effective_tenant = await self._resolve_tenant(token, tenant_raw)
            report_type = request.query.get("report_type")
            reports = await self.service.list_reports(
                uuid.UUID(effective_tenant), report_type
            )
            return web.json_response(
                {"reports": [_report_payload(r, "stored") for r in reports]}
            )
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            return web.json_response({"error": "Internal server error"}, status=500)


def _report_payload(report, status: str) -> dict[str, Any]:
    """JSON-native view of a Report row for the API response."""
    if report is None:
        return {"status": status}
    return {
        "id": str(report.id),
        "tenant_id": str(report.tenant_id),
        "report_type": report.report_type,
        "title": report.title,
        "summary": report.summary,
        "content": report.content,
        "ai_generated": report.ai_generated,
        "model_used": report.model_used,
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "generated_at": report.generated_at.isoformat(),
        "file_path": report.file_path,
        "status": status,
    }