"""Health check endpoint for Evaluation Service."""
from aiohttp import web

from src.service import EvaluationService


class HealthServer:
    def __init__(self, service: EvaluationService):
        self.service = service

    async def health_handler(self, _request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "evaluation"})

    async def metrics_handler(self, _request: web.Request) -> web.Response:
        return web.json_response(self.service.metrics())

    def add_routes(self, app: web.Application) -> None:
        app.router.add_get("/health", self.health_handler)
        app.router.add_get("/metrics", self.metrics_handler)