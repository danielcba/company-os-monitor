"""Insight model + append-only persistence (Reasoning - Restructure).

The Insight concept (core-concepts/insight.md) governs this module: an Insight
is a novel understanding that results from RESTRUCTURING the relationship
between existing knowledge elements - it is not new information, it is a new
organization of information that was already available. "Insight cannot be
forced or scheduled": the Restructure capability only fires when a declarative
rule (procedural memory) detects that the current frame is competitive, and it
always records the transformation that produced the insight (journaling
transformations is an architectural requirement).

P1: an Insight row is append-only and fully immutable. Unlike Hypotheses it has
no lifecycle status field (the schema has no ``status`` column): the row is a
pure transformation journal - once written it is never updated (blocked by the
content trigger) and never deleted. A NEW restructuring over the same context
with a different hypothesis set is a NEW deterministic row, never an UPDATE of
an existing one.

The deterministic ``insight_id`` includes the tenant, the Active Context, the
ordered hypothesis ids it restructures AND the description text, so the same
restructuring over the same knowledge yields the same id (idempotent dedup by
primary key) while a restructuring that covers new hypotheses gets a distinct
id (a new transformation, append-only). ``generated_at`` is deliberately NOT
part of the id: it would break idempotence between runs.
"""
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic insight ids (content-addressed, idempotent).
INSIGHT_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000083")


def insight_id(
    tenant_id: uuid.UUID,
    context_id: uuid.UUID,
    hypothesis_ids: list[uuid.UUID],
    description: str,
) -> uuid.UUID:
    """Derive a deterministic id from the insight content.

    Anchors on the tenant, the Active Context, the ordered hypothesis ids the
    restructuring covers and the description text. Re-generating the SAME
    restructuring over the SAME knowledge yields the same id (dedup by primary
    key); covering a NEW hypothesis changes the id (a new transformation, kept
    as a new append-only row). ``generated_at`` is excluded so re-runs stay
    idempotent.
    """
    ordered_hypotheses = ",".join(str(x) for x in sorted(hypothesis_ids))
    return uuid.uuid5(
        INSIGHT_NAMESPACE,
        f"{tenant_id}:{context_id}:{ordered_hypotheses}:{description}",
    )


class InsightCreate(BaseModel):
    """Creation request for a generated Insight (content only, no lifecycle).

    ``context_id`` is the Active Context the restructuring operates on;
    ``hypothesis_ids`` are the existing Hypotheses whose relationship the
    Insight restructures (the framework: "Insight refines Context and
    Hypothesis"). ``description`` is the new organization of the already
    available knowledge; ``prior_understanding`` records what was understood
    before the restructuring (the transformation journal); ``mental_model_update``
    is the declarative update to the active mental model (JSON, never a claim
    beyond the measured facts). All fields are assigned at generation and never
    retrofitted (P1).
    """

    tenant_id: uuid.UUID
    context_id: uuid.UUID
    hypothesis_ids: list[uuid.UUID]
    description: str
    prior_understanding: str | None = None
    mental_model_update: dict[str, Any] | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Insight(BaseModel):
    """Immutable generated Insight (Reasoning - Restructure).

    Content is immutable (P1) and there is no lifecycle status: an Insight is a
    journaled transformation, never updated and never deleted. The row always
    records the Active Context, the restructured Hypotheses, the new
    organization (``description``), what was understood before
    (``prior_understanding``) and the declarative ``mental_model_update``.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    context_id: uuid.UUID
    hypothesis_ids: list[uuid.UUID]
    description: str
    prior_understanding: str | None = None
    mental_model_update: dict[str, Any] | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


def build_insight(create: InsightCreate) -> Insight:
    """Materialize an Insight from a creation request (id assigned at creation)."""
    return Insight(
        id=insight_id(
            create.tenant_id,
            create.context_id,
            create.hypothesis_ids,
            create.description,
        ),
        tenant_id=create.tenant_id,
        context_id=create.context_id,
        hypothesis_ids=create.hypothesis_ids,
        description=create.description,
        prior_understanding=create.prior_understanding,
        mental_model_update=create.mental_model_update,
        generated_at=create.generated_at,
    )


INSERT_INSIGHT = text(
    """
    INSERT INTO insights (
        id, tenant_id, context_id, hypothesis_ids, description,
        prior_understanding, mental_model_update, generated_at
    )
    VALUES (
        :id, :tenant_id, :context_id, :hypothesis_ids, :description,
        :prior_understanding, :mental_model_update, :generated_at
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, context_id, hypothesis_ids, description,
              prior_understanding, mental_model_update
    """
)

SELECT_INSIGHTS = text(
    """
    SELECT id, tenant_id, context_id, hypothesis_ids, description,
           prior_understanding, mental_model_update, generated_at
    FROM insights
    WHERE tenant_id = :tenant_id
    ORDER BY generated_at
    """
)

SELECT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM insights")


class InsightStore:
    """Persistence gateway for the Insight Store (PostgreSQL insights table)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_insight(self, insight: Insight) -> dict[str, Any] | None:
        """Insert one immutable insight row.

        Returns the persisted row, or None when it was already present
        (idempotent dedup by deterministic id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_INSIGHT,
                {
                    "id": insight.id,
                    "tenant_id": insight.tenant_id,
                    "context_id": insight.context_id,
                    "hypothesis_ids": list(insight.hypothesis_ids),
                    "description": insight.description,
                    "prior_understanding": insight.prior_understanding,
                    "mental_model_update": (
                        json.dumps(insight.mental_model_update)
                        if insight.mental_model_update is not None
                        else None
                    ),
                    "generated_at": insight.generated_at,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            if row is None:
                return None
            persisted = dict(row)
            if isinstance(persisted["hypothesis_ids"], str):
                persisted["hypothesis_ids"] = json.loads(
                    persisted["hypothesis_ids"]
                )
            return persisted

    async def list_insights(self, *, tenant_id: uuid.UUID) -> list[Insight]:
        """Read-only load of the immutable insight rows for a tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_INSIGHTS, {"tenant_id": tenant_id}
            )
            rows = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["hypothesis_ids"], str):
                    row["hypothesis_ids"] = json.loads(row["hypothesis_ids"])
                if isinstance(row["mental_model_update"], str):
                    row["mental_model_update"] = json.loads(
                        row["mental_model_update"]
                    )
                rows.append(Insight(**row))
            return rows

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Insight row."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()