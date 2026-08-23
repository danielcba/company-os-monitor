"""Health endpoint for metacognitive monitoring of the Confidence Calibrator."""
from aiohttp import web

from libs.learning.confidence import ConfidenceStore
from src.service import ConfidenceService


class HealthServer:
    def __init__(self, service: ConfidenceService, confidence_store: ConfidenceStore):
        self.service = service
        self.confidence_store = confidence_store
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
        # Check DB connectivity
        db_healthy = True
        try:
            await self.confidence_store.verify_connection()
        except Exception:
            db_healthy = False

        return web.json_response({
            "status": "healthy" if (self.service.errors == 0 and db_healthy) else "degraded",
            "confidence_scores": self.service.total_confidence_scores,
            "errors": self.service.errors,
            "db_connected": db_healthy,
            "last_run_at": (
                self.service.last_run_at.isoformat()
                if self.service.last_run_at
                else None
            ),
        })

    async def metrics_handler(self, request):
        return web.json_response(self.service.metrics())