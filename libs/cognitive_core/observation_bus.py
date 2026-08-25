"""Observation Bus - Immutable queue using Redis Streams."""
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, Literal

import redis
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis


class Observation(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    source_id: uuid.UUID
    source_type: str  # linux_agent, windows_agent, vmware_agent, etc.
    fact_type: str    # cpu_utilization, memory_usage, disk_usage, event_log, etc.
    fact_value: dict[str, Any]
    unit: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    quality_class: Literal["Q1", "Q2", "Q3", "Q4"]
    raw_payload: dict[str, Any]

    model_config = ConfigDict(frozen=True)  # immutability

class ObservationBus:
    STREAM_KEY = "observations"
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def publish(self, obs: Observation) -> str:
        """Append-only publish. Returns stream entry ID."""
        data = obs.model_dump(mode="json")
        for key in ("fact_value", "raw_payload"):
            data[key] = json.dumps(data[key], default=str)
        return await self.redis.xadd(self.STREAM_KEY, data)

    async def ack(self, group: str, msg_id: str) -> int:
        """Acknowledge a consumed observation once it has been persisted."""
        return await self.redis.xack(self.STREAM_KEY, group, msg_id)
    
    async def consume(
        self, 
        consumer_group: str, 
        consumer: str, 
        count: int = 100, 
        block_ms: int = 5000
    ) -> AsyncGenerator[tuple[str, Observation], None]:
        """Consume up to `count` observations for the Evidence Organizer.

        Returns after a single read round (or after `block_ms` with no new
        messages) so the caller can ack, persist, and organize a batch before
        pulling the next one.
        """
        try:
            await self.redis.xgroup_create(self.STREAM_KEY, consumer_group, id="0", mkstream=True)
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
        entries = await self.redis.xreadgroup(
            consumer_group, consumer, {self.STREAM_KEY: ">"}, count=count, block=block_ms
        )
        for _, messages in entries:
            for msg_id, data in messages:
                for key in ("fact_value", "raw_payload"):
                    data[key] = json.loads(data[key])
                yield msg_id, Observation(**data)