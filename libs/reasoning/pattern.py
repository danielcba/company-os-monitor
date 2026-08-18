"""Pattern model + append-only persistence (Reasoning - Generalize).

P1: a Pattern is immutable once detected; it is only appended. The content
columns (context_id, pattern_type, description, strength_measure, frequency,
detected_at) are assigned at detection and never changed; ``is_active`` is a
lifecycle flag so a newer detection can supersede an older candidate. Per P4 a
pattern is a working regularity: revising it means emitting a NEW library
version (a new ``library_pattern_id``) that produces a new deterministic id,
never an UPDATE of an existing ``patterns`` row.

The deterministic ``pattern_id`` includes the versioned ``library_pattern_id``,
so the exact library version used is traceable in the id and re-running the
detector over the same facts produces the same id (idempotent dedup by primary
key). ``detected_at`` is deliberately NOT part of the id: it would break
idempotence between runs.
"""
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic pattern ids (content-addressed, idempotent).
PATTERN_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-00000000007d")

# Frequency labels measured by the detector (mirrors the library vocabulary).
FREQUENCIES: frozenset[str] = frozenset(
    {"daily", "weekly", "hourly", "event-driven"}
)


def pattern_id(
    tenant_id: uuid.UUID, context_id: uuid.UUID, library_pattern_id: str
) -> uuid.UUID:
    """Derive a deterministic id from the detection content.

    Includes the versioned ``library_pattern_id`` so the library version is
    traceable in the id. Re-detecting over the same context with the same
    library version yields the same id (dedup by primary key); a library
    revision (``_v2``) yields a new id and is appended, never an UPDATE.
    """
    return uuid.uuid5(
        PATTERN_NAMESPACE, f"{tenant_id}:{context_id}:{library_pattern_id}"
    )


class PatternCreate(BaseModel):
    """Creation request for a detected Pattern (content only, no lifecycle).

    ``library_pattern_id`` is not a table column: it only feeds the
    deterministic id and keeps the library version traceable (P4).
    """

    tenant_id: uuid.UUID
    context_id: uuid.UUID
    pattern_type: str
    description: str
    strength_measure: float = Field(ge=0.0, le=1.0)
    frequency: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True
    library_pattern_id: str = ""


class Pattern(BaseModel):
    """Immutable detected Pattern (Reasoning - Generalize).

    Content is immutable (P1); ``is_active`` is a lifecycle flag. The row always
    records the measured support (``strength_measure``), the observed frequency
    and a factual ``description`` of the regularity - never a causal claim (P4).
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    context_id: uuid.UUID
    pattern_type: str
    description: str
    strength_measure: float = Field(ge=0.0, le=1.0)
    frequency: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True

    model_config = ConfigDict(frozen=True)


def build_pattern(create: PatternCreate) -> Pattern:
    """Materialize a Pattern from a creation request (id assigned at creation)."""
    return Pattern(
        id=pattern_id(create.tenant_id, create.context_id, create.library_pattern_id),
        tenant_id=create.tenant_id,
        context_id=create.context_id,
        pattern_type=create.pattern_type,
        description=create.description,
        strength_measure=create.strength_measure,
        frequency=create.frequency,
        detected_at=create.detected_at,
        is_active=create.is_active,
    )


INSERT_PATTERN = text(
    """
    INSERT INTO patterns (
        id, tenant_id, context_id, pattern_type, description,
        strength_measure, frequency, detected_at, is_active
    )
    VALUES (
        :id, :tenant_id, :context_id, :pattern_type, :description,
        :strength_measure, :frequency, :detected_at, :is_active
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, context_id, pattern_type, strength_measure, frequency
    """
)

CHECK_PATTERN_EXISTS = text("SELECT 1 FROM patterns WHERE id = :id")

SELECT_PATTERNS = text(
    """
    SELECT id, tenant_id, context_id, pattern_type, description,
           strength_measure, frequency, detected_at, is_active
    FROM patterns
    WHERE tenant_id = :tenant_id
    ORDER BY detected_at
    """
)

SELECT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM patterns")


class PatternStore:
    """Persistence gateway for the Pattern Store (PostgreSQL patterns table)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_pattern(self, pattern: Pattern) -> dict[str, Any] | None:
        """Insert one immutable pattern row.

        Returns the persisted row, or None when it was already present
        (idempotent dedup by deterministic id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_PATTERN,
                {
                    "id": pattern.id,
                    "tenant_id": pattern.tenant_id,
                    "context_id": pattern.context_id,
                    "pattern_type": pattern.pattern_type,
                    "description": pattern.description,
                    "strength_measure": pattern.strength_measure,
                    "frequency": pattern.frequency,
                    "detected_at": pattern.detected_at,
                    "is_active": pattern.is_active,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def pattern_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating patterns on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_PATTERN_EXISTS, {"id": id})
            return result.scalar() is not None

    async def list_patterns(self, *, tenant_id: uuid.UUID) -> list[Pattern]:
        """Read-only load of the immutable pattern rows for a tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_PATTERNS, {"tenant_id": tenant_id}
            )
            return [Pattern(**dict(row)) for row in result.mappings()]

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Pattern row."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()
