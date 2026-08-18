"""VMware Agent Entry Point - Observation Capturer (vSphere API)."""
import asyncio
import os
import uuid

from libs.cognitive_core.observation_bus import Observation, ObservationBus
from redis.asyncio import Redis

from src.collector import VMwareCollector, connect_vcenter
from src.health import HealthServer


async def main():
    redis_url = os.getenv("OBSERVATION_BUS_URL", "redis://localhost:6379")
    redis = Redis.from_url(redis_url, decode_responses=True)
    bus = ObservationBus(redis)

    tenant_id = uuid.UUID(os.getenv("TENANT_ID", "00000000-0000-0000-0000-000000000001"))
    source_id = uuid.UUID(os.getenv("SOURCE_ID", "00000000-0000-0000-0000-000000000001"))
    interval = int(os.getenv("COLLECTION_INTERVAL_SECONDS", "60"))

    content = connect_vcenter(
        host=os.getenv("VCENTER_HOST", "vcenter"),
        user=os.getenv("VCENTER_USER", ""),
        password=os.getenv("VCENTER_PASSWORD", ""),
        port=int(os.getenv("VCENTER_PORT", "443")),
    )
    collector = VMwareCollector(tenant_id, source_id, content)
    health = HealthServer(collector)

    await health.start()

    while True:
        try:
            observations = collector.capture_all()
            for obs in observations:
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