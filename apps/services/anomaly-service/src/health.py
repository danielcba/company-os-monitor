"""Health endpoint for metacognitive monitoring of the Anomaly Detector."""
from aiohttp import web

from src.service import AnomalyService


class HealthServer:
    def __init__(self, service: AnomalyService):
        self.service = service
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.runner = None

    async def start(self, port: int = 8093):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.service.errors == 0 else "degraded",
            "anomalies": self.service.total_anomalies,
            "errors": self.service.errors,
            "last_run_at": (
                self.service.last_run_at.isoformat()
                if self.service.last_run_at
                else None
            ),
        })

    async def metrics_handler(self, request):
        return web.json_response({
            "total_anomalies": self.service.total_anomalies,
            "total_anomaly_duplicates": self.service.total_duplicates,
            "total_contexts_without_pattern": self.service.total_contexts_without_pattern,
            "total_contexts_without_tolerance": self.service.total_contexts_without_tolerance,
            "total_errors": self.service.errors,
            "anomalies_by_class": dict(self.service.by_class),
            "anomalies_by_mental_model": dict(self.service.by_mental_model),
        })