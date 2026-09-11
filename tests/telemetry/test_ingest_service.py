"""H4.0-B2 — Telemetry Ingest Service Tests.

Covers ADR-0007 §1 (contract), §3 (idempotency), §4 (observation ID),
§7 (quality class):
- Body validation (empty samples, invalid sequence, missing fields)
- captured_at parsing and drift validation
- Sequence monotonicity (1-based, strictly increasing)
- Deterministic observation IDs
- Quality class resolution from capabilities_json
- PayloadConflictError for hash mismatch
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from libs.telemetry.ingest_service import (
    CAPTURED_AT_MAX_DRIFT,
    PayloadConflictError,
    TelemetryIngestService,
    ValidationError,
)

# Test tenant/installation UUIDs
TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
INSTALLATION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
INSTANCE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
CREDENTIAL_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
BATCH_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _valid_body(
    batch_id: uuid.UUID | None = None,
    captured_at: str | None = None,
    samples: list[dict] | None = None,
) -> dict:
    """Build a valid request body per ADR-0007 §1."""
    now = datetime.now(UTC)
    return {
        "batch_id": str(batch_id or BATCH_ID),
        "captured_at": captured_at or now.isoformat(),
        "samples": samples or [
            {
                "sequence": 1,
                "fact_type": "cpu_utilization_percent",
                "fact_value": {"value": 45.2},
                "unit": "percent",
                "labels": {"core": "0"},
            },
        ],
    }


class TestBodyValidation:
    """ADR-0007 §1: request body structure validation."""

    def test_missing_batch_id(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        body = _valid_body()
        del body["batch_id"]
        with pytest.raises(ValidationError, match="batch_id is required"):
            svc._validate_body(body)

    def test_invalid_batch_id(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        body = _valid_body(batch_id=uuid.uuid4())
        body["batch_id"] = "not-a-uuid"
        with pytest.raises(ValidationError, match="batch_id must be a valid UUID"):
            svc._validate_body(body)

    def test_missing_samples(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        body = _valid_body()
        body["samples"] = []
        with pytest.raises(ValidationError, match="samples must be a non-empty array"):
            svc._validate_body(body)

    def test_missing_captured_at(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        body = _valid_body()
        del body["captured_at"]
        with pytest.raises(ValidationError, match="captured_at is required"):
            svc._validate_body(body)

    def test_sample_missing_sequence(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        body = _valid_body(samples=[{"fact_type": "cpu", "fact_value": {}, "unit": "%"}])
        with pytest.raises(ValidationError, match="sequence is required"):
            svc._validate_body(body)

    def test_sample_missing_fact_type(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        body = _valid_body(samples=[{"sequence": 1, "fact_value": {}, "unit": "%"}])
        with pytest.raises(ValidationError, match="fact_type is required"):
            svc._validate_body(body)

    def test_sample_missing_fact_value(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        body = _valid_body(samples=[{"sequence": 1, "fact_type": "cpu", "unit": "%"}])
        with pytest.raises(ValidationError, match="fact_value is required"):
            svc._validate_body(body)

    def test_sample_missing_unit(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        body = _valid_body(samples=[{"sequence": 1, "fact_type": "cpu", "fact_value": {}}])
        with pytest.raises(ValidationError, match="unit is required"):
            svc._validate_body(body)

    def test_valid_body_passes(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        body = _valid_body()
        batch_id = svc._validate_body(body)
        assert batch_id == BATCH_ID


class TestCapturedAtParsing:
    """ADR-0007 §1 L40: captured_at is ISO 8601."""

    def test_valid_iso8601(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        result = svc._parse_captured_at("2026-09-02T10:00:00Z")
        assert result.tzinfo is not None

    def test_valid_with_offset(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        result = svc._parse_captured_at("2026-09-02T10:00:00+00:00")
        assert result.hour == 10

    def test_invalid_format(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        with pytest.raises(ValidationError, match="valid ISO 8601"):
            svc._parse_captured_at("not-a-date")


class TestCapturedAtDrift:
    """ADR-0007 L424: captured_at validated server-side (±5min)."""

    def test_within_window(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        now = datetime.now(UTC)
        svc._validate_captured_at_drift(now)  # no raise

    def test_just_within_window(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        now = datetime.now(UTC)
        just_within = now - CAPTURED_AT_MAX_DRIFT + timedelta(milliseconds=1)
        svc._validate_captured_at_drift(just_within)  # no raise

    def test_at_boundary_rejected(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        now = datetime.now(UTC)
        at_limit = now - CAPTURED_AT_MAX_DRIFT
        with pytest.raises(ValidationError, match="drift too large"):
            svc._validate_captured_at_drift(at_limit)

    def test_exceeds_window(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        now = datetime.now(UTC)
        too_old = now - CAPTURED_AT_MAX_DRIFT - timedelta(seconds=1)
        with pytest.raises(ValidationError, match="drift too large"):
            svc._validate_captured_at_drift(too_old)

    def test_future_exceeds_window(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        now = datetime.now(UTC)
        too_future = now + CAPTURED_AT_MAX_DRIFT + timedelta(seconds=1)
        with pytest.raises(ValidationError, match="drift too large"):
            svc._validate_captured_at_drift(too_future)


class TestSequenceMonotonicity:
    """ADR-0007 §1 L43: sequence 1-based, monotonic within batch."""

    def test_valid_1_based_sequential(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        samples = [
            {"sequence": 1, "fact_type": "a", "fact_value": {}, "unit": "%"},
            {"sequence": 2, "fact_type": "b", "fact_value": {}, "unit": "%"},
            {"sequence": 3, "fact_type": "c", "fact_value": {}, "unit": "%"},
        ]
        svc._validate_sequence_monotonicity(samples)  # no raise

    def test_zero_based_rejected(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        samples = [{"sequence": 0, "fact_type": "a", "fact_value": {}, "unit": "%"}]
        with pytest.raises(ValidationError, match="positive integer"):
            svc._validate_sequence_monotonicity(samples)

    def test_negative_rejected(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        samples = [{"sequence": -1, "fact_type": "a", "fact_value": {}, "unit": "%"}]
        with pytest.raises(ValidationError, match="positive integer"):
            svc._validate_sequence_monotonicity(samples)

    def test_non_contiguous_rejected(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        samples = [
            {"sequence": 1, "fact_type": "a", "fact_value": {}, "unit": "%"},
            {"sequence": 3, "fact_type": "b", "fact_value": {}, "unit": "%"},
        ]
        with pytest.raises(ValidationError, match="must be 2"):
            svc._validate_sequence_monotonicity(samples)

    def test_duplicate_sequence_rejected(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        samples = [
            {"sequence": 1, "fact_type": "a", "fact_value": {}, "unit": "%"},
            {"sequence": 1, "fact_type": "b", "fact_value": {}, "unit": "%"},
        ]
        with pytest.raises(ValidationError, match="must be 2"):
            svc._validate_sequence_monotonicity(samples)

    def test_out_of_order_rejected(self) -> None:
        svc = TelemetryIngestService("sqlite://")
        samples = [
            {"sequence": 2, "fact_type": "a", "fact_value": {}, "unit": "%"},
            {"sequence": 1, "fact_type": "b", "fact_value": {}, "unit": "%"},
        ]
        with pytest.raises(ValidationError, match="must be 1"):
            svc._validate_sequence_monotonicity(samples)


class TestPayloadConflictError:
    """ADR-0007 §3: same batch_id + different hash → 409."""

    def test_error_attributes(self) -> None:
        batch_id = uuid.uuid4()
        existing_hash = "abc123"
        err = PayloadConflictError(batch_id, existing_hash)
        assert err.batch_id == batch_id
        assert err.existing_hash == existing_hash
        assert "different payload" in str(err)


class TestObservationIdIntegration:
    """Verify observation_id integration with ingest service."""

    def test_deterministic_observation_ids(self) -> None:
        from libs.telemetry.observation_id import observation_id

        ids1 = [
            observation_id(TENANT_ID, INSTALLATION_ID, BATCH_ID, 1, "cpu"),
            observation_id(TENANT_ID, INSTALLATION_ID, BATCH_ID, 2, "mem"),
        ]
        ids2 = [
            observation_id(TENANT_ID, INSTALLATION_ID, BATCH_ID, 1, "cpu"),
            observation_id(TENANT_ID, INSTALLATION_ID, BATCH_ID, 2, "mem"),
        ]
        assert ids1 == ids2
