"""Health endpoint for metacognitive monitoring of the Pattern Detector."""
from aiohttp import web

from src.service import PatternService


class HealthServer:
    def __init__(self, service: PatternService):
        self.service = service
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.runner = None

    async def start(self, port: int = 8092):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.service.errors == 0 else "degraded",
            "patterns": self.service.total_patterns,
            "errors": self.service.errors,
            "last_run_at": (
                self.service.last_run_at.isoformat()
                if self.service.last_run_at
                else None
            ),
        })

    async def metrics_handler(self, request):
        return web.json_response({
            "total_patterns": self.service.total_patterns,
            "total_pattern_duplicates": self.service.total_duplicates,
            "total_candidates_below_threshold": self.service.total_below_threshold,
            "total_errors": self.service.errors,
            "patterns_by_type": dict(self.service.by_type),
            "patterns_by_mental_model": dict(self.service.by_mental_model),
        })
