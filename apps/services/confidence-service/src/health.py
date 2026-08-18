"""Health endpoint for metacognitive monitoring of the Confidence Calibrator."""
from aiohttp import web

from src.service import ConfidenceService


class HealthServer:
    def __init__(self, service: ConfidenceService):
        self.service = service
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.runner = None

    async def start(self, port: int = 8095):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.service.errors == 0 else "degraded",
            "confidence_scores": self.service.total_confidence_scores,
            "errors": self.service.errors,
            "last_run_at": (
                self.service.last_run_at.isoformat()
                if self.service.last_run_at
                else None
            ),
        })

    async def metrics_handler(self, request):
        return web.json_response(self.service.metrics())