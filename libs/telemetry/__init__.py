"""Telemetry ingestion library (H4.0-B2, ADR-0007)."""
from libs.telemetry.canonical import canonical_float, canonical_payload, payload_hash
from libs.telemetry.ingest_service import (
    IngestResult,
    PayloadConflictError,
    TelemetryIngestService,
    ValidationError,
)
from libs.telemetry.observation_id import OBSERVATION_NAMESPACE, observation_id
from libs.telemetry.publisher import ObservationPublisher

__all__ = [
    "canonical_float",
    "canonical_payload",
    "payload_hash",
    "IngestResult",
    "ObservationPublisher",
    "OBSERVATION_NAMESPACE",
    "PayloadConflictError",
    "TelemetryIngestService",
    "ValidationError",
    "observation_id",
]
