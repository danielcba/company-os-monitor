"""Health endpoint for metacognitive monitoring of the Hypothesis Generator."""
from aiohttp import web

from src.service import HypothesisService


class HealthServer:
    def __init__(self, service: HypothesisService):
        self.service = service
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.runner = None

    async def start(self, port: int = 8094):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.service.errors == 0 else "degraded",
            "hypotheses": self.service.total_hypotheses,
            "errors": self.service.errors,
            "last_run_at": (
                self.service.last_run_at.isoformat()
                if self.service.last_run_at
                else None
            ),
        })

    async def metrics_handler(self, request):
        return web.json_response({
            "total_hypotheses": self.service.total_hypotheses,
            "total_hypothesis_duplicates": self.service.total_duplicates,
            "total_anomalies_no_templates": self.service.total_anomalies_no_templates,
            "total_errors": self.service.errors,
            "hypotheses_by_status": dict(self.service.by_status),
            "hypotheses_by_mental_model": dict(self.service.by_mental_model),
        })