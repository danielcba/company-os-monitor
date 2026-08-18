"""Health endpoint for metacognitive monitoring of the Evidence Organizer."""
from aiohttp import web

from src.consumer import ObservationConsumer


class HealthServer:
    def __init__(self, consumer: ObservationConsumer):
        self.consumer = consumer
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.runner = None

    async def start(self, port: int = 8090):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.consumer.errors == 0 else "degraded",
            "processed": self.consumer.processed,
            "errors": self.consumer.errors,
            "last_processed_at": (
                self.consumer.last_processed_at.isoformat()
                if self.consumer.last_processed_at
                else None
            ),
        })

    async def metrics_handler(self, request):
        return web.json_response({
            "total_processed": self.consumer.processed,
            "total_duplicates": self.consumer.duplicates,
            "total_errors": self.consumer.errors,
            "total_evidence": self.consumer.evidence_created,
            "total_evidence_duplicates": self.consumer.evidence_duplicates,
            "total_evidence_errors": self.consumer.evidence_errors,
            "evidence_by_type": dict(self.consumer.evidence_by_type),
        })