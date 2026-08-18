"""Health endpoint for metacognitive monitoring of the Context Activator."""
from aiohttp import web

from src.service import ContextService


class HealthServer:
    def __init__(self, service: ContextService):
        self.service = service
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.runner = None

    async def start(self, port: int = 8091):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.service.errors == 0 else "degraded",
            "contexts": self.service.contexts_activated,
            "errors": self.service.errors,
            "last_run_at": (
                self.service.last_run_at.isoformat()
                if self.service.last_run_at
                else None
            ),
        })

    async def metrics_handler(self, request):
        return web.json_response({
            "total_contexts": self.service.contexts_activated,
            "total_context_duplicates": self.service.contexts_duplicates,
            "total_errors": self.service.errors,
            "contexts_by_mental_model": dict(self.service.by_mental_model),
            "contexts_by_purpose": dict(self.service.by_purpose),
        })