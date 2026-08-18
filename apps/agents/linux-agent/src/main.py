"""Linux Agent Entry Point - Observation Capturer."""
import asyncio
import os
import uuid

from libs.cognitive_core.observation_bus import Observation, ObservationBus
from redis.asyncio import Redis

from src.collector import LinuxCollector
from src.health import HealthServer


async def main():
    redis_url = os.getenv("OBSERVATION_BUS_URL", "redis://localhost:6379")
    redis = Redis.from_url(redis_url, decode_responses=True)
    bus = ObservationBus(redis)
    
    tenant_id = uuid.UUID(os.getenv("TENANT_ID", "00000000-0000-0000-0000-000000000001"))
    source_id = uuid.UUID(os.getenv("SOURCE_ID", "00000000-0000-0000-0000-000000000001"))
    interval = int(os.getenv("COLLECTION_INTERVAL_SECONDS", "60"))
    
    collector = LinuxCollector(tenant_id, source_id)
    health = HealthServer(collector)
    
    # Start health endpoint
    await health.start()
    
    # Collection loop
    while True:
        try:
            observations = collector.capture_all()
            for obs in observations:
                # Convert to Observation with metadata
                full_obs = Observation(
                    id=uuid.uuid4(),
                    tenant_id=obs.tenant_id,
                    source_id=obs.source_id,
                    source_type=obs.source_type,
                    fact_type=obs.fact_type,
                    fact_value=obs.fact_value,
                    unit=obs.unit,
                    quality_class=obs.quality_class,
                    raw_payload=obs.raw_payload,
                )
                await bus.publish(full_obs)
                health.record_capture()
        except Exception as e:
            health.record_error(e)
        
        await asyncio.sleep(interval)

if __name__ == "__main__":
    asyncio.run(main())