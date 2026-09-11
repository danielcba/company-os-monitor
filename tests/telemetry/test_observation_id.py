"""H4.0-B2 — Deterministic Observation ID Tests.

Covers ADR-0007 §4:
- Determinism: same input → same ID
- Different inputs → different IDs
- Namespace consistency
- UUIDv5 format validation
"""
from __future__ import annotations

import uuid

import pytest

from libs.telemetry.observation_id import (
    OBSERVATION_NAMESPACE,
    observation_id,
)

# Fixed test vectors
TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
INSTALLATION = uuid.UUID("22222222-2222-2222-2222-222222222222")
BATCH = uuid.UUID("33333333-3333-3333-3333-333333333333")


class TestObservationIdDeterminism:
    """ADR-0007 §4: same input → same observation_id."""

    def test_same_input_same_id(self) -> None:
        id1 = observation_id(TENANT, INSTALLATION, BATCH, 1, "cpu_utilization_percent")
        id2 = observation_id(TENANT, INSTALLATION, BATCH, 1, "cpu_utilization_percent")
        assert id1 == id2

    def test_repeated_calls_stable(self) -> None:
        ids = [
            observation_id(TENANT, INSTALLATION, BATCH, 1, "cpu_utilization_percent")
            for _ in range(100)
        ]
        assert len(set(ids)) == 1


class TestObservationIdUniqueness:
    """ADR-0007 §4: different inputs → different IDs."""

    @pytest.mark.parametrize(
        "fieldoverride",
        [
            {"sequence": 2},
            {"fact_type": "memory_usage"},
            {"tenant_id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")},
            {"installation_id": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")},
            {"batch_id": uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")},
        ],
        ids=["sequence", "fact_type", "tenant", "installation", "batch"],
    )
    def test_different_input_different_id(self, fieldoverride: dict) -> None:
        base = observation_id(TENANT, INSTALLATION, BATCH, 1, "cpu_utilization_percent")
        kwargs = {
            "tenant_id": TENANT,
            "installation_id": INSTALLATION,
            "batch_id": BATCH,
            "sequence": 1,
            "fact_type": "cpu_utilization_percent",
        }
        kwargs.update(fieldoverride)
        other = observation_id(**kwargs)
        assert base != other


class TestObservationIdFormat:
    """UUIDv5 format validation."""

    def test_returns_uuid(self) -> None:
        result = observation_id(TENANT, INSTALLATION, BATCH, 1, "cpu_utilization_percent")
        assert isinstance(result, uuid.UUID)

    def test_version_5(self) -> None:
        result = observation_id(TENANT, INSTALLATION, BATCH, 1, "cpu_utilization_percent")
        assert result.version == 5

    def test_namespace_constant(self) -> None:
        assert uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8") == OBSERVATION_NAMESPACE


class TestObservationIdMultipleSamples:
    """Batch with multiple samples produces distinct IDs."""

    def test_sequential_samples_unique(self) -> None:
        ids = [
            observation_id(TENANT, INSTALLATION, BATCH, i, "fact")
            for i in range(1, 6)
        ]
        assert len(set(ids)) == 5

    def test_different_fact_types_unique(self) -> None:
        facts = ["cpu_utilization_percent", "memory_usage", "disk_usage", "network_throughput"]
        ids = [observation_id(TENANT, INSTALLATION, BATCH, 1, f) for f in facts]
        assert len(set(ids)) == len(facts)
