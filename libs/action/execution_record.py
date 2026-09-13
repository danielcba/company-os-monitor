"""Execution Record model + append-only persistence (H6 — Execution & Outcome Contract).

An ExecutionRecord represents an explicit, auditable, manually/externally-recorded
act of executing a committed Decision. It does NOT imply that the system executed
anything automatically.

Relationship:
    Decision 1 ─── 0..N ExecutionRecord
    ExecutionRecord 1 ─── 0..1 Outcome (OutcomeRevision)

P1: append-only — content columns immutable once written.
P6: execution is explicitly recorded, never assumed.
R1: single capability — record execution of a committed Decision.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic execution record ids (content-addressed).
EXECUTION_RECORD_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000083")

# Execution statuses — explicit, auditable states.
STATUS_EXECUTED = "executed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_UNKNOWN = "unknown"
EXECUTION_STATUSES: frozenset[str] = frozenset(
    {STATUS_EXECUTED, STATUS_FAILED, STATUS_CANCELLED, STATUS_UNKNOWN}
)


def execution_record_id(
    tenant_id: uuid.UUID,
    decision_id: uuid.UUID,
    executed_at: datetime,
) -> uuid.UUID:
    """Derive a deterministic id from the execution record content.

    Anchors on tenant, decision, and execution time. Re-recording the same
    execution at the same time produces the same id (idempotent dedup).
    """
    return uuid.uuid5(
        EXECUTION_RECORD_NAMESPACE,
        f"{tenant_id}:{decision_id}:{executed_at.isoformat()}",
    )


class ExecutionRecordCreate(BaseModel):
    """Creation request for an execution record (H6).

    Fields mirror the ``execution_records`` table. The record explicitly states
    that a Decision was executed (manually or externally), when it happened,
    and optionally who did it and what the result was.
    """

    tenant_id: uuid.UUID
    decision_id: uuid.UUID
    execution_status: str = STATUS_EXECUTED
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    executed_by: uuid.UUID | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class ExecutionRecord(BaseModel):
    """Immutable execution record row (H6 — append-only, P1).

    Content is immutable (P1). The record captures:
    - WHAT was executed (decision_id)
    - WHEN it was executed (executed_at)
    - WHO recorded it (executed_by)
    - WHAT the result was (execution_status)
    - Additional context (notes, metadata)
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    decision_id: uuid.UUID
    execution_status: str
    executed_at: datetime
    executed_by: uuid.UUID | None
    notes: str | None
    metadata: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(frozen=True)


def build_execution_record(create: ExecutionRecordCreate) -> ExecutionRecord:
    """Materialize an ExecutionRecord from a creation request (id at creation)."""
    return ExecutionRecord(
        id=execution_record_id(
            create.tenant_id,
            create.decision_id,
            create.executed_at,
        ),
        tenant_id=create.tenant_id,
        decision_id=create.decision_id,
        execution_status=create.execution_status,
        executed_at=create.executed_at,
        executed_by=create.executed_by,
        notes=create.notes,
        metadata=create.metadata,
        created_at=datetime.now(UTC),
    )


INSERT_EXECUTION_RECORD = text(
    """
    INSERT INTO execution_records (
        id, tenant_id, decision_id, execution_status, executed_at,
        executed_by, notes, metadata
    )
    VALUES (
        :id, :tenant_id, :decision_id, :execution_status, :executed_at,
        :executed_by, :notes, CAST(:metadata AS jsonb)
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, decision_id, execution_status, executed_at,
              executed_by, notes, metadata, created_at
    """
)

SELECT_EXECUTION_RECORDS_BY_DECISION = text(
    """
    SELECT id, tenant_id, decision_id, execution_status, executed_at,
           executed_by, notes, metadata, created_at
    FROM execution_records
    WHERE tenant_id = :tenant_id AND decision_id = :decision_id
    ORDER BY created_at DESC
    """
)

SELECT_EXECUTION_RECORDS_BY_TENANT = text(
    """
    SELECT id, tenant_id, decision_id, execution_status, executed_at,
           executed_by, notes, metadata, created_at
    FROM execution_records
    WHERE tenant_id = :tenant_id
    ORDER BY created_at DESC
    """
)


class ExecutionRecordStore:
    """Persistence gateway for the Execution Records Store (PostgreSQL)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_execution_record(
        self, record: ExecutionRecord
    ) -> dict[str, Any] | None:
        """Insert one immutable execution record (append-only, P1).

        Returns the persisted row, or None when it was already present
        (idempotent dedup by the deterministic content-addressed id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_EXECUTION_RECORD,
                {
                    "id": record.id,
                    "tenant_id": record.tenant_id,
                    "decision_id": record.decision_id,
                    "execution_status": record.execution_status,
                    "executed_at": record.executed_at,
                    "executed_by": record.executed_by,
                    "notes": record.notes,
                    "metadata": (
                        json.dumps(record.metadata, default=str)
                        if record.metadata
                        else "{}"
                    ),
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def list_execution_records_by_decision(
        self, *, tenant_id: uuid.UUID, decision_id: uuid.UUID
    ) -> list[ExecutionRecord]:
        """Read-only load of execution records for a specific decision."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_EXECUTION_RECORDS_BY_DECISION,
                {"tenant_id": tenant_id, "decision_id": decision_id},
            )
            return [self._row_to_record(row) for row in result.mappings()]

    async def list_execution_records_by_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> list[ExecutionRecord]:
        """Read-only load of all execution records for a tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_EXECUTION_RECORDS_BY_TENANT,
                {"tenant_id": tenant_id},
            )
            return [self._row_to_record(row) for row in result.mappings()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _row_to_record(mapping) -> ExecutionRecord:
        row = dict(mapping)
        if isinstance(row["metadata"], str):
            row["metadata"] = json.loads(row["metadata"])
        return ExecutionRecord(**row)
