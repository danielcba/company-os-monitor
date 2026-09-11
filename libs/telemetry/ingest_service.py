"""Telemetry Ingest Service — business logic for POST /api/v1/telemetry/ingest.

Implements ADR-0007 §1 (contract), §3 (idempotency), §4 (deterministic
observation ID), §5 (tenant-aware relationships), §7 (quality class).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from libs.telemetry.canonical import canonical_payload, payload_hash
from libs.telemetry.observation_id import observation_id

CAPTURED_AT_MAX_DRIFT = timedelta(minutes=5)


class PayloadConflictError(Exception):
    """Same batch_id with different payload hash → 409 Conflict (ADR-0007 §3)."""

    def __init__(self, batch_id: uuid.UUID, existing_hash: str) -> None:
        self.batch_id = batch_id
        self.existing_hash = existing_hash
        super().__init__(
            "batch_id already exists with different payload"
        )


class ValidationError(Exception):
    """Input validation failure → 400 Bad Request."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class IngestResult:
    """Successful ingestion response data (ADR-0007 §1)."""

    batch_id: uuid.UUID
    observation_ids: list[uuid.UUID]
    ingested_at: datetime


class TelemetryIngestService:
    """Business logic for telemetry ingestion.

    Uses asyncpg directly (matching existing gateway pattern in service.py).
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def ingest_batch(
        self,
        tenant_id: uuid.UUID,
        installation_id: uuid.UUID,
        instance_id: uuid.UUID,
        credential_id: uuid.UUID,
        body: dict[str, Any],
    ) -> IngestResult:
        """Process a telemetry batch per ADR-0007 §1,§3,§4,§7.

        Validates input, checks idempotency, persists atomically.
        Raises PayloadConflictError on 409, ValidationError on 400.
        """
        batch_id = self._validate_body(body)
        samples = body["samples"]
        captured_at_str = body["captured_at"]

        captured_at = self._parse_captured_at(captured_at_str)
        self._validate_sequence_monotonicity(samples)

        canonical_bytes = canonical_payload(body)
        hash_value = payload_hash(canonical_bytes)

        self._validate_captured_at_drift(captured_at)

        installation = await self._resolve_installation(tenant_id, installation_id)
        if installation is None:
            raise ValidationError("installation not found or tenant mismatch")

        server_id = installation["server_id"]
        caps_raw = installation["capabilities_json"]
        capabilities = json.loads(caps_raw) if isinstance(caps_raw, str) else (caps_raw or {})
        quality_mapping = capabilities.get("quality_mapping", {})
        default_qc = capabilities.get("default_quality_class", "Q3")

        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                await conn.execute("SAVEPOINT sp_batch")
                try:
                    await conn.execute(
                        "INSERT INTO metric_batches "
                        "(id, tenant_id, installation_id, instance_id, credential_id, "
                        " batch_id, payload_hash, captured_at, sample_count) "
                        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                        batch_id, tenant_id, installation_id, instance_id, credential_id,
                        batch_id, hash_value, captured_at, len(samples),
                    )
                except asyncpg.UniqueViolationError:
                    await conn.execute("ROLLBACK TO SAVEPOINT sp_batch")
                    existing = await conn.fetchrow(
                        "SELECT id, payload_hash, received_at FROM metric_batches "
                        "WHERE tenant_id = $1 AND installation_id = $2 AND batch_id = $3",
                        tenant_id, installation_id, batch_id,
                    )
                    if existing is not None and existing["payload_hash"] == hash_value:
                        obs_ids = await self._fetch_existing_observation_ids(
                            conn, tenant_id, batch_id
                        )
                        return IngestResult(
                            batch_id=batch_id,
                            observation_ids=obs_ids,
                            ingested_at=existing["received_at"],
                        )
                    existing_hash = existing["payload_hash"] if existing else "unknown"
                    raise PayloadConflictError(batch_id, existing_hash)

                observation_ids: list[uuid.UUID] = []
                outbox_observations: list[dict[str, Any]] = []
                for sample in samples:
                    seq = sample["sequence"]
                    fact_type = sample["fact_type"]
                    obs_id = observation_id(
                        tenant_id, installation_id, batch_id, seq, fact_type
                    )
                    observation_ids.append(obs_id)

                    quality_class = quality_mapping.get(fact_type, default_qc)

                    await conn.execute(
                        "INSERT INTO metric_samples "
                        "(tenant_id, batch_id, sequence, fact_type, fact_value, unit, labels) "
                        "VALUES ($1,$2,$3,$4,$5,$6,$7)",
                        tenant_id, batch_id, seq, fact_type,
                        __import__("json").dumps(sample.get("fact_value", {})),
                        sample.get("unit", ""),
                        __import__("json").dumps(sample.get("labels", {})),
                    )

                    outbox_observations.append({
                        "id": str(obs_id),
                        "tenant_id": str(tenant_id),
                        "source_id": str(server_id),
                        "source_type": installation.get("agent_type", "unknown"),
                        "fact_type": fact_type,
                        "fact_value": sample.get("fact_value", {}),
                        "unit": sample.get("unit", ""),
                        "captured_at": captured_at.isoformat(),
                        "quality_class": quality_class,
                        "raw_payload": sample,
                    })

                combined_observation = {
                    "batch_id": str(batch_id),
                    "observation_ids": [str(oid) for oid in observation_ids],
                    "observations": outbox_observations,
                }
                await conn.execute(
                    "INSERT INTO observation_outbox "
                    "(tenant_id, installation_id, batch_id, credential_id, "
                    " payload_hash, observation) "
                    "VALUES ($1,$2,$3,$4,$5,$6)",
                    tenant_id, installation_id, batch_id, credential_id,
                    hash_value, json.dumps(combined_observation),
                )

            return IngestResult(
                batch_id=batch_id,
                observation_ids=observation_ids,
                ingested_at=datetime.now(UTC),
            )
        finally:
            await conn.close()

    def _validate_body(self, body: dict[str, Any]) -> uuid.UUID:
        """Validate request body structure per ADR-0007 §1. Returns batch_id."""
        if not isinstance(body, dict):
            raise ValidationError("request body must be a JSON object")

        batch_id_raw = body.get("batch_id")
        if batch_id_raw is None:
            raise ValidationError("batch_id is required")
        try:
            batch_id = uuid.UUID(str(batch_id_raw))
        except ValueError:
            raise ValidationError("batch_id must be a valid UUID") from None

        samples = body.get("samples")
        if not isinstance(samples, list) or len(samples) == 0:
            raise ValidationError("samples must be a non-empty array")

        if "captured_at" not in body:
            raise ValidationError("captured_at is required")

        for i, sample in enumerate(samples):
            if not isinstance(sample, dict):
                raise ValidationError(f"samples[{i}] must be a JSON object")
            if "sequence" not in sample:
                raise ValidationError(f"samples[{i}].sequence is required")
            if "fact_type" not in sample:
                raise ValidationError(f"samples[{i}].fact_type is required")
            if "fact_value" not in sample:
                raise ValidationError(f"samples[{i}].fact_value is required")
            if "unit" not in sample:
                raise ValidationError(f"samples[{i}].unit is required")

        return batch_id

    def _parse_captured_at(self, captured_at_raw: str) -> datetime:
        """Parse captured_at as ISO 8601. Raises ValidationError."""
        try:
            return datetime.fromisoformat(captured_at_raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise ValidationError("captured_at must be a valid ISO 8601 timestamp") from None

    def _validate_captured_at_drift(self, captured_at: datetime) -> None:
        """Validate captured_at is within ±5min of server time (ADR-0007 L424)."""
        now = datetime.now(UTC)
        drift = abs((now - captured_at).total_seconds())
        if drift >= CAPTURED_AT_MAX_DRIFT.total_seconds():
            max_secs = int(CAPTURED_AT_MAX_DRIFT.total_seconds())
            raise ValidationError(
                f"captured_at drift too large: {drift:.0f}s (max {max_secs}s)"
            )

    def _validate_sequence_monotonicity(self, samples: list[dict]) -> None:
        """Validate 1-based monotonic sequences (ADR-0007 §1 L43, L425)."""
        expected = 1
        for i, sample in enumerate(samples):
            seq = sample.get("sequence")
            if not isinstance(seq, int) or seq < 1:
                raise ValidationError(
                    f"samples[{i}].sequence must be a positive integer"
                )
            if seq != expected:
                raise ValidationError(
                    f"samples[{i}].sequence must be {expected}, got {seq} "
                    "(sequences must be 1-based and monotonic)"
                )
            expected = seq + 1

    async def _resolve_installation(
        self, tenant_id: uuid.UUID, installation_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """Resolve installation → server_id, capabilities_json (ADR-0007 §5 L320-325)."""
        conn = await asyncpg.connect(self._dsn)
        try:
            return await conn.fetchrow(
                "SELECT server_id, capabilities_json, agent_type "
                "FROM agent_installations "
                "WHERE id = $1 AND tenant_id = $2 AND status = 'ACTIVE'",
                installation_id, tenant_id,
            )
        finally:
            await conn.close()

    async def _fetch_existing_observation_ids(
        self, conn: asyncpg.Connection, tenant_id: uuid.UUID, batch_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Fetch observation IDs from outbox for idempotent return (ADR-0007 §3 L216)."""
        row = await conn.fetchrow(
            "SELECT observation FROM observation_outbox "
            "WHERE tenant_id = $1 AND batch_id = $2",
            tenant_id, batch_id,
        )
        if row is None:
            return []
        obs = row["observation"]
        if isinstance(obs, str):
            obs = json.loads(obs)
        ids_raw = obs.get("observation_ids", [])
        return [uuid.UUID(str(oid)) for oid in ids_raw]
