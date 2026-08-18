"""Health endpoint for metacognitive monitoring."""
import os
from datetime import UTC, datetime

from aiohttp import web

from src.collector import VMwareCollector


class HealthServer:
    def __init__(self, collector: VMwareCollector):
        self.collector = collector
        self.last_capture = None
        self.error_count = 0
        self.capture_count = 0
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.runner = None

    async def start(self, port: int = 8082):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    def record_capture(self):
        self.last_capture = datetime.now(UTC)
        self.capture_count += 1

    def record_error(self, error: Exception):
        self.error_count += 1

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.error_count == 0 else "degraded",
            "last_capture": self.last_capture.isoformat() if self.last_capture else None,
            "error_count": self.error_count,
            "capture_count": self.capture_count,
        })

    async def metrics_handler(self, request):
        interval = int(os.getenv("COLLECTION_INTERVAL_SECONDS", "60"))
        return web.json_response({
            "capture_latency_ms": 0,
            "observations_per_minute": 60 / interval,
            "total_captures": self.capture_count,
            "total_errors": self.error_count,
        })