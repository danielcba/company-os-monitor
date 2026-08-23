"""Context Service Entry Point - Context Activator (Evidence -> Active Context).

The Perception Layer's Explain capability: reads immutable Evidence from
Postgres, runs the explanatory coherence competition per tenant + purpose (P2),
and writes the selected Active Context into ``contexts``.
"""
import asyncio
import logging
import os

from libs.perception.context import ContextStore
from libs.perception.evidence import EvidenceStore
from libs.shared.graceful_shutdown import GracefulShutdown

from src.activator import ActivatorEngine
from src.health import HealthServer
from src.service import ContextService

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("ACTIVATOR_HEALTH_PORT", "8091"))
    cycle_seconds = float(os.getenv("ACTIVATION_CYCLE_SECONDS", "30"))

    evidence_store = EvidenceStore(dsn)
    context_store = ContextStore(dsn)
    await evidence_store.verify_connection()
    await context_store.verify_connection()

    service = ContextService(
        evidence_store,
        context_store,
        engine=ActivatorEngine(),
    )
    health = HealthServer(service)

    await health.start(port)

    shutdown = GracefulShutdown()
    shutdown.install()

    while not shutdown.should_exit.is_set():
        try:
            await service.run_activation_cycle()
        except Exception:
            logger.exception("Error in context activation cycle")
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())