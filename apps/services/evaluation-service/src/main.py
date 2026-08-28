"""Evaluation Service - Main entry point."""
import asyncio
import logging
import os
import signal
import sys

from aiohttp import web
from libs.learning.confidence import ConfidenceStore
from libs.perception.evidence import EvidenceStore
from libs.reasoning.evaluation import EvaluationStore
from libs.reasoning.hypothesis import HypothesisStore

from src.health import HealthServer
from src.service import EvaluationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

DSN = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor",
)

# Port must not collide with decision-service (8097). 8102 is free in the
# service port map (see start.sh SERVICE_SPECS).
PORT = int(os.getenv("EVALUATION_HEALTH_PORT", "8102"))
BATCH_SIZE = int(os.getenv("EVALUATION_BATCH_SIZE", "500"))
INTERVAL_SECONDS = int(os.getenv("EVALUATION_INTERVAL_SECONDS", "60"))


async def run_service() -> None:
    hypothesis_store = HypothesisStore(DSN)
    evidence_store = EvidenceStore(DSN)
    confidence_store = ConfidenceStore(DSN)
    evaluation_store = EvaluationStore(DSN)

    await hypothesis_store.verify_connection()
    await evidence_store.verify_connection()
    await confidence_store.verify_connection()
    await evaluation_store.verify_connection()

    service = EvaluationService(
        hypothesis_store=hypothesis_store,
        evidence_store=evidence_store,
        confidence_store=confidence_store,
        evaluation_store=evaluation_store,
        batch_size=BATCH_SIZE,
    )

    health = HealthServer(service)
    app = web.Application()
    health.add_routes(app)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("Evaluation Service HTTP started on port %s", PORT)

    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        log.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    async def evaluation_loop() -> None:
        while not stop_event.is_set():
            try:
                log.info("Starting evaluation cycle")
                count = await service.run_evaluation_cycle()
                log.info("Evaluation cycle completed: %d evaluations", count)
            except Exception:  # noqa: BLE001
                log.exception("Evaluation cycle failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=INTERVAL_SECONDS)
            except TimeoutError:
                continue

    await asyncio.gather(evaluation_loop(), stop_event.wait())

    log.info("Shutting down...")
    await runner.cleanup()
    await hypothesis_store.close()
    await evidence_store.close()
    await confidence_store.close()
    await evaluation_store.close()


def main() -> None:
    try:
        asyncio.run(run_service())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
