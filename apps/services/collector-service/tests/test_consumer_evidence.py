"""Unit tests for the ObservationConsumer evidence pipeline (mocked bus/stores)
and for the /metrics evidence counters."""
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from libs.cognitive_core.observation_bus import Observation

from src.consumer import ObservationConsumer
from src.health import HealthServer
from src.organizer import OrganizerConfig, OrganizerEngine

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
SOURCE = uuid.UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime.now(UTC)


def resource_observations() -> list[Observation]:
    def make(fact_type, value):
        return Observation(
            tenant_id=TENANT,
            source_id=SOURCE,
            source_type="linux_agent",
            fact_type=fact_type,
            fact_value=value,
            unit="percent",
            captured_at=NOW,
            quality_class="Q1",
            raw_payload={},
        )

    return [
        make("cpu_utilization_percent", {"value": 96.0}),
        make("memory_usage", {"used_bytes": 90, "total_bytes": 100}),
        make("disk_usage", {"used_bytes": 92, "total_bytes": 100}),
    ]


class FakeBus:
    def __init__(self, entries):
        self.entries = list(entries)
        self.acked = []

    async def ack(self, group, msg_id):
        self.acked.append(msg_id)

    async def consume(self, group, consumer, count=100, block_ms=5000):
        for msg_id, obs in self.entries:
            yield msg_id, obs


class FakeObservationStore:
    async def observation_exists(self, *, id, captured_at):
        return False

    async def save_observation(self, observation):
        return {"id": observation.id}


class FakeEvidenceStore:
    def __init__(self):
        self.saved = {}
        self.duplicate_ids = []

    async def save_evidence(self, evidence):
        if evidence.id in self.saved:
            self.duplicate_ids.append(evidence.id)
            return None
        self.saved[evidence.id] = evidence
        return {"id": evidence.id, "organization_type": evidence.organization_type}


def make_bus():
    return FakeBus([(f"1-{i}", obs) for i, obs in enumerate(resource_observations())])


def make_consumer(bus, evidence_store):
    return ObservationConsumer(
        bus,
        FakeObservationStore(),
        evidence_store=evidence_store,
        organizer=OrganizerEngine(OrganizerConfig()),
    )


@pytest.fixture
def evidence_store():
    return FakeEvidenceStore()


async def test_consumer_organizes_evidence_after_batch(evidence_store):
    bus = make_bus()
    consumer = make_consumer(bus, evidence_store)

    processed = await consumer.process_batch()

    assert processed == 3
    assert consumer.processed == 3
    assert consumer.evidence_created == 1
    assert consumer.evidence_duplicates == 0
    assert consumer.evidence_by_type["resource_exhaustion_evidence"] == 1
    assert len(evidence_store.saved) == 1
    saved = next(iter(evidence_store.saved.values()))
    assert saved.organization_type == "resource_exhaustion_evidence"
    assert saved.quality_class.value == "Q1"
    assert saved.weight == 0.875
    assert len(saved.observation_ids) == 3


async def test_consumer_does_not_organize_without_evidence_store():
    bus = make_bus()
    consumer = ObservationConsumer(bus, FakeObservationStore())
    await consumer.process_batch()
    assert consumer.evidence_created == 0


async def test_consumer_dedups_evidence_on_reorganization(evidence_store):
    bus = make_bus()
    consumer = make_consumer(bus, evidence_store)

    await consumer.process_batch()
    assert consumer.evidence_created == 1

    await consumer.process_batch()
    assert consumer.evidence_created == 1
    assert consumer.evidence_duplicates == 1
    assert len(evidence_store.saved) == 1


async def test_consumer_counts_evidence_errors():
    class FailingEvidenceStore(FakeEvidenceStore):
        async def save_evidence(self, evidence):
            raise RuntimeError("db down")

    consumer = make_consumer(make_bus(), FailingEvidenceStore())
    await consumer.process_batch()
    assert consumer.evidence_errors == 1
    assert consumer.evidence_created == 0


def test_metrics_exposes_evidence_counters():
    consumer = SimpleNamespace(
        processed=10,
        duplicates=2,
        errors=0,
        evidence_created=4,
        evidence_duplicates=1,
        evidence_errors=0,
        evidence_by_type={"resource_exhaustion_evidence": 3, "backup_failure_evidence": 1},
        last_processed_at=None,
    )
    health = HealthServer(consumer)

    import asyncio

    async def get_metrics():
        from aiohttp import web

        response = await health.metrics_handler(SimpleNamespace())
        body = json.loads(response.body)
        assert body["total_evidence"] == 4
        assert body["total_evidence_duplicates"] == 1
        assert body["evidence_by_type"]["resource_exhaustion_evidence"] == 3
        assert isinstance(response, web.Response)

    asyncio.run(get_metrics())