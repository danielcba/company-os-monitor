"""Evidence model + append-only persistence (Perception - Organize).

P1 enforcement: Evidence is immutable. It can only be appended; an immutable
evidence row organizes existing observations and never modifies them. The
database trigger blocks any UPDATE/DELETE on the evidence table.
"""
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from libs.perception.observation import EvidenceCreate, QualityClass

# Fixed namespace for deterministic evidence ids (content-addressed, idempotent).
EVIDENCE_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-00000000007b")


def evidence_id(
    tenant_id: uuid.UUID,
    organization_type: str,
    observation_ids: list[uuid.UUID],
) -> uuid.UUID:
    """Derive a deterministic id from the evidence content.

    Re-organizing the same observations for the same organization type yields
    the same id, which makes re-runs idempotent (dedup by primary key).
    """
    ordered = ",".join(str(x) for x in sorted(observation_ids))
    return uuid.uuid5(EVIDENCE_NAMESPACE, f"{tenant_id}:{organization_type}:{ordered}")


class Evidence(BaseModel):
    """Immutable organization of one or more Observations (P1)."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    observation_ids: list[uuid.UUID]
    organization_type: str
    description: str  # objective/factual - never interpretation or prediction
    quality_class: QualityClass
    weight: float = Field(ge=0.0, le=1.0)
    organized_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


def build_evidence(create: EvidenceCreate) -> Evidence:
    """Materialize an Evidence from a creation request (id assigned at creation)."""
    return Evidence(
        id=evidence_id(create.tenant_id, create.organization_type, create.observation_ids),
        tenant_id=create.tenant_id,
        observation_ids=create.observation_ids,
        organization_type=create.organization_type,
        description=create.description,
        quality_class=create.quality_class,
        weight=create.weight,
    )


INSERT_EVIDENCE = text(
    """
    INSERT INTO evidence (
        id, tenant_id, observation_ids, organization_type,
        description, quality_class, weight, organized_at
    )
    VALUES (
        :id, :tenant_id, :observation_ids, :organization_type,
        :description, :quality_class, :weight, :organized_at
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, organization_type, quality_class, weight
    """
)

CHECK_EVIDENCE_EXISTS = text("SELECT 1 FROM evidence WHERE id = :id")

SELECT_EVIDENCE = text(
    """
    SELECT id, tenant_id, observation_ids, organization_type, description,
           quality_class, weight, organized_at
    FROM evidence
    WHERE tenant_id = :tenant_id
    ORDER BY organized_at DESC
    """
)

SELECT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM evidence")


class EvidenceStore:
    """Persistence gateway for the Evidence Store (PostgreSQL evidence table)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_evidence(self, evidence: Evidence) -> dict[str, Any] | None:
        """Insert one immutable evidence row. Returns the persisted row, or None
        when it was already present (idempotent dedup)."""
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_EVIDENCE,
                {
                    "id": evidence.id,
                    "tenant_id": evidence.tenant_id,
                    "observation_ids": list(evidence.observation_ids),
                    "organization_type": evidence.organization_type,
                    "description": evidence.description,
                    "quality_class": evidence.quality_class.value,
                    "weight": evidence.weight,
                    "organized_at": evidence.organized_at,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def evidence_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating evidence on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(
                CHECK_EVIDENCE_EXISTS, {"id": id}
            )
            return result.scalar() is not None

    async def list_evidence(self, *, tenant_id: uuid.UUID) -> list[Evidence]:
        """Read-only load of the immutable evidence rows for a tenant.

        Used by the Context Activator (Explain) as its input batch. Evidence is
        never modified here; rows are materialized back into the frozen Evidence
        model so the competition runs over the same P1 immutable data.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_EVIDENCE, {"tenant_id": tenant_id}
            )
            return [Evidence(**dict(row)) for row in result.mappings()]

    async def list_evidence_since(
        self, *, tenant_id: uuid.UUID, since: datetime
    ) -> list[Evidence]:
        """Load Evidence organized at or after ``since`` (inclusive).

        Used by the Evaluate capability to fetch only the knowledge produced
        after a Hypothesis was generated. Evidence is the canonical Perception
        artifact consumed by Reasoning/Evaluate (never raw Observations).
        """
        rows = await self.list_evidence(tenant_id=tenant_id)
        return [ev for ev in rows if ev.organized_at >= since]

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Evidence row (competition inputs)."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()