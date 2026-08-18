"""Context Service Entry Point - Context Activator (Evidence -> Active Context).

The Perception Layer's Explain capability: reads immutable Evidence from
Postgres, runs the explanatory coherence competition per tenant + purpose (P2),
and writes the selected Active Context into ``contexts``.
"""
import asyncio
import os

from libs.perception.context import ContextStore
from libs.perception.evidence import EvidenceStore

from src.activator import ActivatorEngine
from src.health import HealthServer
from src.service import ContextService


async def main():
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

    while True:
        await service.run_activation_cycle()
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())