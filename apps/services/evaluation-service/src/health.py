"""Health and metrics endpoints for the Evaluation Service.

/health is a readiness probe: it reports healthy only when the database the
service depends on is reachable. Reporting "healthy" while the DB is down would
mask an operational failure (Blocker #12). /metrics exposes the operational
counters required to observe the evaluation loop.
"""
from aiohttp import web

from src.service import EvaluationService


class HealthServer:
    def __init__(self, service: EvaluationService):
        self.service = service

    async def health_handler(self, _request: web.Request) -> web.Response:
        try:
            await self.service.evaluation_store.verify_connection()
        except Exception:  # noqa: BLE001 - DB unreachable => not ready
            return web.json_response(
                {
                    "status": "unhealthy",
                    "service": "evaluation",
                    "reason": "database unreachable",
                },
                status=503,
            )
        return web.json_response({"status": "healthy", "service": "evaluation"})

    async def metrics_handler(self, _request: web.Request) -> web.Response:
        return web.json_response(self.service.metrics())

    def add_routes(self, app: web.Application) -> None:
        app.router.add_get("/health", self.health_handler)
        app.router.add_get("/metrics", self.metrics_handler)
