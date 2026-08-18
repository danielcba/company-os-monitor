"""Anomaly model + append-only persistence (Reasoning - Detect Deviation).

P1: an Anomaly is immutable once detected; it is only appended. All content
columns (context_id, pattern_id, deviation_score, tolerance_threshold,
anomaly_class, detected_at) are assigned at detection and never retrofitted;
``anomalies`` has no ``is_active`` lifecycle flag, so the row is fully
immutable (UPDATE and DELETE are blocked by the content trigger, like
``evidence``).

The deterministic ``anomaly_id`` includes the tenant, the Active Context and
the expected Pattern it deviates from, so re-detecting over the same facts
produces the same id (idempotent dedup by primary key). ``detected_at`` is
deliberately NOT part of the id: it would break idempotence between runs.
"""
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic anomaly ids (content-addressed, idempotent).
ANOMALY_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-00000000007e")

# Anomaly classes per the framework spec. The Sprint 6 MVP implements only
# ``point``; contextual and collective are reserved for later sprints.
ANOMALY_CLASS_POINT = "point"
ANOMALY_CLASS_CONTEXTUAL = "contextual"
ANOMALY_CLASS_COLLECTIVE = "collective"
ANOMALY_CLASSES: frozenset[str] = frozenset(
    {ANOMALY_CLASS_POINT, ANOMALY_CLASS_CONTEXTUAL, ANOMALY_CLASS_COLLECTIVE}
)


def anomaly_id(
    tenant_id: uuid.UUID, context_id: uuid.UUID, pattern_id: uuid.UUID
) -> uuid.UUID:
    """Derive a deterministic id from the detection content.

    Anchors on the tenant, the Active Context and the expected Pattern it
    deviates from. Re-detecting over the same context+pattern yields the same
    id (dedup by primary key); a different context or pattern yields a new id
    and is appended, never an UPDATE.
    """
    return uuid.uuid5(
        ANOMALY_NAMESPACE, f"{tenant_id}:{context_id}:{pattern_id}"
    )


class AnomalyCreate(BaseModel):
    """Creation request for a detected Anomaly (content only, no lifecycle)."""

    tenant_id: uuid.UUID
    context_id: uuid.UUID
    pattern_id: uuid.UUID
    deviation_score: float = Field(ge=0.0)
    tolerance_threshold: float = Field(ge=0.0)
    anomaly_class: str = ANOMALY_CLASS_POINT
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Anomaly(BaseModel):
    """Immutable detected Anomaly (Reasoning - Detect Deviation).

    Content is immutable (P1) and there is no lifecycle flag. The row always
    records the quantified ``deviation_score``, the explicit auditable
    ``tolerance_threshold`` it exceeded and the ``anomaly_class``. It only
    signals a deviation - it never explains it (explanation belongs to
    Hypothesis) and never triggers actions.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    context_id: uuid.UUID
    pattern_id: uuid.UUID
    deviation_score: float = Field(ge=0.0)
    tolerance_threshold: float = Field(ge=0.0)
    anomaly_class: str = ANOMALY_CLASS_POINT
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


def build_anomaly(create: AnomalyCreate) -> Anomaly:
    """Materialize an Anomaly from a creation request (id assigned at creation)."""
    return Anomaly(
        id=anomaly_id(create.tenant_id, create.context_id, create.pattern_id),
        tenant_id=create.tenant_id,
        context_id=create.context_id,
        pattern_id=create.pattern_id,
        deviation_score=create.deviation_score,
        tolerance_threshold=create.tolerance_threshold,
        anomaly_class=create.anomaly_class,
        detected_at=create.detected_at,
    )


INSERT_ANOMALY = text(
    """
    INSERT INTO anomalies (
        id, tenant_id, context_id, pattern_id,
        deviation_score, tolerance_threshold, anomaly_class, detected_at
    )
    VALUES (
        :id, :tenant_id, :context_id, :pattern_id,
        :deviation_score, :tolerance_threshold, :anomaly_class, :detected_at
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, context_id, pattern_id,
              deviation_score, tolerance_threshold, anomaly_class
    """
)

CHECK_ANOMALY_EXISTS = text("SELECT 1 FROM anomalies WHERE id = :id")

SELECT_ANOMALIES = text(
    """
    SELECT id, tenant_id, context_id, pattern_id,
           deviation_score, tolerance_threshold, anomaly_class, detected_at
    FROM anomalies
    WHERE tenant_id = :tenant_id
    ORDER BY detected_at
    """
)

SELECT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM anomalies")


class AnomalyStore:
    """Persistence gateway for the Anomaly Store (PostgreSQL anomalies table)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_anomaly(self, anomaly: Anomaly) -> dict[str, Any] | None:
        """Insert one immutable anomaly row.

        Returns the persisted row, or None when it was already present
        (idempotent dedup by deterministic id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_ANOMALY,
                {
                    "id": anomaly.id,
                    "tenant_id": anomaly.tenant_id,
                    "context_id": anomaly.context_id,
                    "pattern_id": anomaly.pattern_id,
                    "deviation_score": anomaly.deviation_score,
                    "tolerance_threshold": anomaly.tolerance_threshold,
                    "anomaly_class": anomaly.anomaly_class,
                    "detected_at": anomaly.detected_at,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def anomaly_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating anomalies on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_ANOMALY_EXISTS, {"id": id})
            return result.scalar() is not None

    async def list_anomalies(self, *, tenant_id: uuid.UUID) -> list[Anomaly]:
        """Read-only load of the immutable anomaly rows for a tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_ANOMALIES, {"tenant_id": tenant_id}
            )
            return [Anomaly(**dict(row)) for row in result.mappings()]

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Anomaly row."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()