"""Recommendation model + append-only persistence (Action - Propose).

The Recommendation concept (core-concepts/recommendation.md) governs this
module: a Recommendation is a proposed course of action derived from the
current understanding (the leading Hypothesis) and its calibrated Confidence
(Sprint 8). "A recommendation is an offer. A decision is a commitment." The
good recommendation states what to do, why, what is expected to happen, how
confident the system is and what alternatives were considered - all advisory
and reversible (P6: the Recommendation never executes anything; commitment and
authority belong to the Decision, Sprint 10).

P1 enforcement: a ``recommendations`` row is append-only. The deterministic
``recommendation_id`` is content-addressed: it hashes the tenant, the leading
Hypothesis, the specific calibrated Confidence row and the action description,
deliberately EXCLUDING ``proposed_at`` so re-formulating the same offer over
the same inputs produces the same id (idempotent dedup by primary key). The
row is never deleted and its content columns are immutable (blocked by the
content trigger); only ``status`` is a lifecycle field
(proposed -> accepted/rejected/superseded, decided by the Decision layer).

MVP: recommendations are formed ONLY over Hypotheses (``insight_id`` stays
NULL; Insight is a future sprint) and ALWAYS carry a calibrated Confidence
(R4): no recommendation without ``confidence_id``.
"""
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic recommendation ids (content-addressed, idempotent).
RECOMMENDATION_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000081")

# Lifecycle of the offer: status is the ONLY flippable column (content is
# immutable, P1). A recommendation starts advisory (``proposed``) and is
# accepted/rejected/superseded by the Decision layer (Sprint 10).
STATUS_PROPOSED = "proposed"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"
STATUS_SUPERSEDED = "superseded"
RECOMMENDATION_STATUSES: frozenset[str] = frozenset(
    {STATUS_PROPOSED, STATUS_ACCEPTED, STATUS_REJECTED, STATUS_SUPERSEDED}
)


def recommendation_id(
    tenant_id: uuid.UUID,
    hypothesis_id: uuid.UUID,
    confidence_id: uuid.UUID,
    action_description: str,
) -> uuid.UUID:
    """Derive a deterministic id from the recommendation content.

    Anchors on the tenant, the leading Hypothesis, the specific calibrated
    Confidence row that supports the offer and the action description. Two
    different offers over the same understanding get distinct ids; re-forming
    the SAME offer over the SAME inputs yields the same id (dedup by primary
    key). ``proposed_at`` is deliberately excluded: it would break idempotence
    between runs. Binding ``confidence_id`` (not just the hypothesis) means a
    NEW calibration of the same hypothesis produces a NEW recommendation row
    (append-only, P1) instead of silently reusing the old offer.
    """
    return uuid.uuid5(
        RECOMMENDATION_NAMESPACE,
        f"{tenant_id}:{hypothesis_id}:{confidence_id}:{action_description}",
    )


class RecommendationCreate(BaseModel):
    """Creation request for a proposed Recommendation (content only).

    Fields mirror the ``recommendations`` table (docs/01).
    ``expected_consequences`` are observable, verifiable predictions in concrete
    terms; ``alternatives_considered`` is a list of the other options evaluated,
    each with its rationale and the reason it was not chosen. ``confidence_score``
    is the CALIBRATED score of the leading Hypothesis (Sprint 8) - the
    Recommendation never recalibrates confidence (R4: it carries the score and
    its reasons, already computed).
    """

    tenant_id: uuid.UUID
    hypothesis_id: uuid.UUID
    insight_id: uuid.UUID | None = None
    confidence_id: uuid.UUID
    action_description: str
    rationale: str
    expected_consequences: list[str] = Field(default_factory=list)
    alternatives_considered: list[dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    status: str = STATUS_PROPOSED
    proposed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


class Recommendation(BaseModel):
    """Immutable proposed Recommendation (Action - Propose).

    Content is immutable (P1); ``status`` is a lifecycle field
    (proposed -> accepted/rejected/superseded). The row always records the
    offer (``action_description``), the traceable ``rationale`` (evidence/
    hypothesis/confidence), the observable ``expected_consequences``, the
    ``alternatives_considered`` with their rationale and the calibrated
    ``confidence_score`` - advisory and reversible, never executed here.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    hypothesis_id: uuid.UUID
    insight_id: uuid.UUID | None = None
    confidence_id: uuid.UUID
    action_description: str
    rationale: str
    expected_consequences: list[str] = Field(default_factory=list)
    alternatives_considered: list[dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    status: str = STATUS_PROPOSED
    proposed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


def build_recommendation(create: RecommendationCreate) -> Recommendation:
    """Materialize a Recommendation from a creation request (id at creation)."""
    return Recommendation(
        id=recommendation_id(
            create.tenant_id,
            create.hypothesis_id,
            create.confidence_id,
            create.action_description,
        ),
        tenant_id=create.tenant_id,
        hypothesis_id=create.hypothesis_id,
        insight_id=create.insight_id,
        confidence_id=create.confidence_id,
        action_description=create.action_description,
        rationale=create.rationale,
        expected_consequences=create.expected_consequences,
        alternatives_considered=create.alternatives_considered,
        confidence_score=create.confidence_score,
        status=create.status,
        proposed_at=create.proposed_at,
    )


INSERT_RECOMMENDATION = text(
    """
    INSERT INTO recommendations (
        id, tenant_id, hypothesis_id, insight_id, confidence_id,
        action_description, rationale, expected_consequences,
        alternatives_considered, confidence_score, status, proposed_at
    )
    VALUES (
        :id, :tenant_id, :hypothesis_id, :insight_id, :confidence_id,
        :action_description, :rationale, CAST(:expected_consequences AS jsonb),
        CAST(:alternatives_considered AS jsonb), :confidence_score, :status,
        :proposed_at
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, hypothesis_id, insight_id, confidence_id,
              action_description, rationale, confidence_score, status
    """
)

CHECK_RECOMMENDATION_EXISTS = text("SELECT 1 FROM recommendations WHERE id = :id")

SELECT_RECOMMENDATIONS = text(
    """
    SELECT id, tenant_id, hypothesis_id, insight_id, confidence_id,
           action_description, rationale, expected_consequences,
           alternatives_considered, confidence_score, status, proposed_at
    FROM recommendations
    WHERE tenant_id = :tenant_id
    ORDER BY proposed_at
    """
)

SELECT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM recommendations")


class RecommendationStore:
    """Persistence gateway for the Recommendation Store (PostgreSQL recommendations)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_recommendation(
        self, recommendation: Recommendation
    ) -> dict[str, Any] | None:
        """Insert one immutable recommendation row (append-only).

        Returns the persisted row, or None when it was already present
        (idempotent dedup by the deterministic content-addressed id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_RECOMMENDATION,
                {
                    "id": recommendation.id,
                    "tenant_id": recommendation.tenant_id,
                    "hypothesis_id": recommendation.hypothesis_id,
                    "insight_id": recommendation.insight_id,
                    "confidence_id": recommendation.confidence_id,
                    "action_description": recommendation.action_description,
                    "rationale": recommendation.rationale,
                    "expected_consequences": json.dumps(
                        list(recommendation.expected_consequences)
                    ),
                    "alternatives_considered": json.dumps(
                        recommendation.alternatives_considered, default=str
                    ),
                    "confidence_score": recommendation.confidence_score,
                    "status": recommendation.status,
                    "proposed_at": recommendation.proposed_at,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def recommendation_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating recommendations on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_RECOMMENDATION_EXISTS, {"id": id})
            return result.scalar() is not None

    async def list_recommendations(self, *, tenant_id: uuid.UUID) -> list[Recommendation]:
        """Read-only load of the immutable recommendation rows for a tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_RECOMMENDATIONS, {"tenant_id": tenant_id}
            )
            rows = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["expected_consequences"], str):
                    row["expected_consequences"] = json.loads(
                        row["expected_consequences"]
                    )
                if isinstance(row["alternatives_considered"], str):
                    row["alternatives_considered"] = json.loads(
                        row["alternatives_considered"]
                    )
                rows.append(Recommendation(**row))
            return rows

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Recommendation row."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()