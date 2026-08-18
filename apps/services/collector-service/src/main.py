"""Collector Service Entry Point - Evidence Organizer (Observations -> Evidence)."""
import asyncio
import os

from libs.cognitive_core.observation_bus import ObservationBus
from libs.perception.evidence import EvidenceStore
from libs.perception.store import ObservationStore
from redis.asyncio import Redis

from src.consumer import ObservationConsumer
from src.health import HealthServer
from src.organizer import OrganizerConfig, OrganizerEngine


async def main():
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

    while True:
        try:
            await consumer.process_batch()
        except Exception:
            consumer.errors += 1
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())