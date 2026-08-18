"""Unit tests for the ObservationConsumer (mocked bus and store)."""
import uuid

import pytest
from libs.cognitive_core.observation_bus import Observation

from src.consumer import ObservationConsumer

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
SOURCE = uuid.UUID("00000000-0000-0000-0000-000000000002")


def make_observation() -> Observation:
    return Observation(
        tenant_id=TENANT,
        source_id=SOURCE,
        source_type="linux_agent",
        fact_type="cpu_utilization_percent",
        fact_value={"value": 42.0},
        unit="percent",
        quality_class="Q1",
        raw_payload={},
    )


class FakeBus:
    def __init__(self, entries):
        self.entries = list(entries)
        self.acked = []

    async def ack(self, group, msg_id):
        self.acked.append(msg_id)

    async def consume(self, group, consumer, count=100, block_ms=5000):
        for msg_id, obs in self.entries:
            yield msg_id, obs


class FakeStore:
    def __init__(self, existing=(), fail_on_save=False):
        self.existing = set(existing)
        self.saved = []
        self.fail_on_save = fail_on_save

    async def observation_exists(self, *, id, captured_at):
        return id in self.existing

    async def save_observation(self, observation):
        if self.fail_on_save:
            raise RuntimeError("db down")
        self.saved.append(observation)
        return {"id": observation.id}


@pytest.fixture
def obs1():
    return "1630000000000-0", make_observation()


@pytest.fixture
def obs2():
    updated = make_observation().model_copy(update={"fact_type": "memory_usage"})
    return "1630000000000-1", updated


async def test_persists_and_acks(obs1, obs2):
    bus = FakeBus([obs1, obs2])
    store = FakeStore()
    consumer = ObservationConsumer(bus, store)

    processed = await consumer.process_batch()

    assert processed == 2
    assert len(store.saved) == 2
    assert store.saved[0].fact_type == "cpu_utilization_percent"
    assert store.saved[1].fact_type == "memory_usage"
    assert set(bus.acked) == {"1630000000000-0", "1630000000000-1"}
    assert consumer.processed == 2


async def test_duplicates_are_acked_not_resaved(obs1):
    bus = FakeBus([obs1])
    store = FakeStore(existing=[obs1[1].id])
    consumer = ObservationConsumer(bus, store)

    processed = await consumer.process_batch()

    assert processed == 1
    assert store.saved == []
    assert bus.acked == ["1630000000000-0"]
    assert consumer.duplicates == 1


async def test_failure_leaves_message_pending(obs1):
    bus = FakeBus([obs1])
    store = FakeStore(fail_on_save=True)
    consumer = ObservationConsumer(bus, store)

    processed = await consumer.process_batch()

    assert processed == 0
    assert bus.acked == []
    assert consumer.errors == 1
    assert consumer.processed == 0