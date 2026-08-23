"""HTTP surface for the Report service: /health, /metrics, /api/v1/reports.

The Report service is non-canonical (ADR-0002): it exposes the report
generate/list endpoints plus operational metrics (no rule numbers). The
generate endpoint accepts ``type`` (executive/technical/json) and an optional
``tenant_id``; without a tenant it generates for every tenant that has
committed Decisions.

Protected endpoints require a valid Bearer JWT token (enforced by the
jwt_auth_middleware from libs.access.middleware).
"""
import uuid
from typing import Any

from aiohttp import web

from src.service import RENDERABLE_TYPES, ReportService


class ReportServer:
    def __init__(self, service: ReportService):
        self.service = service
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
        tenant_raw = request.query.get("tenant_id")
        try:
            generated = []
            if tenant_raw:
                report, status = await self.service.generate(
                    uuid.UUID(tenant_raw), report_type
                )
                generated.append(_report_payload(report, status))
            else:
                for tenant_id in await self.service.decision_store.list_tenant_ids():
                    report, status = await self.service.generate(tenant_id, report_type)
                    generated.append(_report_payload(report, status))
            return web.json_response({"generated": generated})
        except Exception as exc:  # noqa: BLE001 - surface as API error
            return web.json_response({"error": str(exc)}, status=500)

    async def list_handler(self, request):
        tenant_raw = request.query.get("tenant_id")
        if not tenant_raw:
            return web.json_response(
                {"error": "tenant_id query parameter is required"}, status=400
            )
        report_type = request.query.get("report_type")
        try:
            reports = await self.service.list_reports(
                uuid.UUID(tenant_raw), report_type
            )
            return web.json_response(
                {"reports": [_report_payload(r, "stored") for r in reports]}
            )
        except Exception as exc:  # noqa: BLE001 - surface as API error
            return web.json_response({"error": str(exc)}, status=500)


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