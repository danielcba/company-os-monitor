"""Learning Memory ledger (P7 persistence, authorized 2026-08-27).

Persists the learning signal derived by the P7 read/compute capabilities
(Pattern Refinement, Context Revision, Insight Transformation) into a NEW
entity ``learning_memory``. Each POST appends an immutable-by-record row;
idempotency is enforced by a UNIQUE index on
``(tenant_id, target_type, target_id, signal_hash)`` so re-persisting an
identical signal is a no-op (no duplicate row).

Canonical entities are NEVER mutated (P1): this is a separate, append-only
ledger. The gateway consumes it via its read store; this module lives in
``libs.memory`` (NOT libs.reasoning / libs.perception) per the gateway
boundary (R3, ADR-0002). The DB write path is exercised only by the
explicit, authorized POST endpoint.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

TARGET_TYPES = frozenset({"pattern", "context", "insight"})


@dataclass(slots=True)
class PersistLearningMemoryInput:
    tenant_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    signal: dict[str, Any]
    provenance: dict[str, Any]


@dataclass(slots=True)
class LearningMemoryRecord:
    id: uuid.UUID
    tenant_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    signal: dict[str, Any]
    provenance: dict[str, Any]
    signal_hash: str
    created_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "target_type": self.target_type,
            "target_id": str(self.target_id),
            "signal": self.signal,
            "provenance": self.provenance,
            "signal_hash": self.signal_hash,
            "created_at": self.created_at.isoformat(),
        }


def compute_signal_hash(signal: dict[str, Any]) -> str:
    """Deterministic SHA-256 of a signal for idempotent persistence."""
    canonical = json.dumps(
        signal, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@runtime_checkable
class MemoryStoreProtocol(Protocol):
    """Contract for the Learning Memory ledger store (testable seam)."""

    async def persist(self, *, record: PersistLearningMemoryInput) -> LearningMemoryRecord:
        ...

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
    ) -> list[LearningMemoryRecord]:
        ...

    async def get_latest(
        self, *, tenant_id: uuid.UUID, target_type: str, target_id: uuid.UUID
    ) -> LearningMemoryRecord | None:
        ...


_INSERT_SQL = text(
    """
    INSERT INTO learning_memory
        (tenant_id, target_type, target_id, signal, provenance, signal_hash)
    VALUES
        (:tenant_id, :target_type, :target_id, :signal::jsonb, :provenance::jsonb, :signal_hash)
    ON CONFLICT (tenant_id, target_type, target_id, signal_hash) DO NOTHING
    RETURNING id, tenant_id, target_type, target_id, signal, provenance,
              signal_hash, created_at
    """
)

_LIST_SQL = text(
    """
    SELECT id, tenant_id, target_type, target_id, signal, provenance,
           signal_hash, created_at
    FROM learning_memory
    WHERE tenant_id = :tenant_id
      AND (:target_type::text IS NULL OR target_type = :target_type::text)
      AND (:target_id IS NULL OR target_id = :target_id)
    ORDER BY created_at DESC
    """
)

_GET_LATEST_SQL = text(
    """
    SELECT id, tenant_id, target_type, target_id, signal, provenance,
           signal_hash, created_at
    FROM learning_memory
    WHERE tenant_id = :tenant_id
      AND target_type = :target_type::text
      AND target_id = :target_id
    ORDER BY created_at DESC
    LIMIT 1
    """
)


def _row_to_record(row) -> LearningMemoryRecord:
    return LearningMemoryRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        signal=row["signal"],
        provenance=row["provenance"],
        signal_hash=row["signal_hash"],
        created_at=row["created_at"],
    )


class MemoryStore:
    """Append-only ledger of learned adjustments (P7 persistence).

    Mirrors the gateway write-store pattern (own async engine + sessionmaker).
    """

    def __init__(
        self,
        dsn: str | None = None,
        engine: AsyncEngine | None = None,
    ) -> None:
        if engine is not None:
            self._engine = engine
            self._owns_engine = False
        elif dsn:
            self._engine = create_async_engine(dsn)
            self._owns_engine = True
        else:
            raise ValueError("MemoryStore requires dsn or engine")  # noqa: TRY003
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def persist(self, *, record: PersistLearningMemoryInput) -> LearningMemoryRecord:
        if record.target_type not in TARGET_TYPES:
            raise ValueError(f"invalid target_type: {record.target_type}")  # noqa: TRY003
        signal_hash = compute_signal_hash(record.signal)
        async with self._session_factory() as session:
            result = await session.execute(
                _INSERT_SQL,
                {
                    "tenant_id": record.tenant_id,
                    "target_type": record.target_type,
                    "target_id": record.target_id,
                    "signal": json.dumps(record.signal, default=str),
                    "provenance": json.dumps(record.provenance, default=str),
                    "signal_hash": signal_hash,
                },
            )
            row = result.mappings().one_or_none()
            if row is None:
                # Idempotent no-op: identical signal already persisted.
                existing = await self.get_latest(
                    tenant_id=record.tenant_id,
                    target_type=record.target_type,
                    target_id=record.target_id,
                )
                if existing is not None:
                    return existing
            await session.commit()
            if row is not None:
                return _row_to_record(row)
        # Fallback: re-fetch after commit (defensive).
        return (await self.get_latest(  # type: ignore[return-value]
            tenant_id=record.tenant_id,
            target_type=record.target_type,
            target_id=record.target_id,
        ))

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
    ) -> list[LearningMemoryRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                _LIST_SQL,
                {
                    "tenant_id": tenant_id,
                    "target_type": target_type,
                    "target_id": target_id,
                },
            )
            return [_row_to_record(r) for r in result.mappings().all()]

    async def get_latest(
        self, *, tenant_id: uuid.UUID, target_type: str, target_id: uuid.UUID
    ) -> LearningMemoryRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                _GET_LATEST_SQL,
                {
                    "tenant_id": tenant_id,
                    "target_type": target_type,
                    "target_id": target_id,
                },
            )
            row = result.mappings().one_or_none()
            return _row_to_record(row) if row is not None else None

    async def verify_connection(self) -> None:
        async with self._session_factory() as session:
            await session.execute(text("SELECT 1"))

    async def close(self) -> None:
        if self._owns_engine:
            await self._engine.dispose()
