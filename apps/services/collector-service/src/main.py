"""Collector Service Entry Point - Evidence Organizer (Observations -> Evidence)."""
import asyncio
import logging
import os

from libs.cognitive_core.observation_bus import ObservationBus
from libs.perception.evidence import EvidenceStore
from libs.perception.store import ObservationStore
from libs.shared.graceful_shutdown import GracefulShutdown
from redis.asyncio import Redis

from src.consumer import ObservationConsumer
from src.health import HealthServer
from src.organizer import OrganizerConfig, OrganizerEngine

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    redis_url = os.getenv("OBSERVATION_BUS_URL", "redis://localhost:6379")
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    group = os.getenv("CONSUMER_GROUP", "evidence_organizers")
    consumer_name = os.getenv("CONSUMER_NAME", "collector-1")
    port = int(os.getenv("HEALTH_PORT", "8090"))

    redis = Redis.from_url(redis_url, decode_responses=True)
    store = ObservationStore(dsn)
    evidence_store = EvidenceStore(dsn)
    await store.verify_connection()
    await evidence_store.verify_connection()

    bus = ObservationBus(redis)
    consumer = ObservationConsumer(
        bus,
        store,
        group,
        consumer_name,
        evidence_store=evidence_store,
        organizer=OrganizerEngine(OrganizerConfig.from_env()),
    )
    health = HealthServer(consumer)

    await health.start(port)

    shutdown = GracefulShutdown()
    shutdown.install()

    while not shutdown.should_exit.is_set():
        try:
            await consumer.process_batch()
        except Exception:
            consumer.errors += 1
            logger.exception("Error processing observation batch")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())