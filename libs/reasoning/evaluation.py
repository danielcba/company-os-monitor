"""Hypothesis Evaluation model + append-only persistence (Reasoning - Evaluate).

P1: an Evaluation is immutable once created; it is only appended. All content
columns (hypothesis_id, evidence_ids, observed_outcomes, support_count,
contradiction_count, confidence_id, result, rationale, evaluated_at) are
assigned at evaluation and never retrofitted. The row is never deleted
(persistent audit trail; enforced by the content trigger).

The deterministic ``evaluation_id`` includes the tenant, the hypothesis, the
evidence used and the result, so re-evaluating the same hypothesis with the
same evidence produces the same id (idempotent dedup by primary key), while
new evidence yields a new row: the evaluation history is preserved as an
append-only audit trail (P1) instead of being overwritten.
"""
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic evaluation ids (content-addressed, idempotent).
EVALUATION_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000083")

# Evaluation result lifecycle.
RESULT_CONFIRMED = "confirmed"
RESULT_FALSIFIED = "falsified"
RESULT_INSUFFICIENT = "insufficient"
EVALUATION_RESULTS: frozenset[str] = frozenset(
    {RESULT_CONFIRMED, RESULT_FALSIFIED, RESULT_INSUFFICIENT}
)


def evaluation_id(
    tenant_id: uuid.UUID,
    hypothesis_id: uuid.UUID,
    evidence_ids: list[uuid.UUID],
    result: str,
) -> uuid.UUID:
    """Derive a deterministic id from the evaluation content.

    Anchors on the tenant, the hypothesis being evaluated, the evidence used
    and the result. Two evaluations of the same hypothesis with the SAME
    evidence and result yield the same id (idempotent dedup by primary key);
    a re-evaluation with DIFFERENT evidence or result yields a DIFFERENT id -
    so the old row is never updated and the history is kept (append-only, P1).
    ``evaluated_at`` is deliberately excluded: it would break idempotence
    between runs.
    """
    ordered_evidence = ",".join(str(x) for x in sorted(evidence_ids))
    return uuid.uuid5(
        EVALUATION_NAMESPACE,
        f"{tenant_id}:{hypothesis_id}:{ordered_evidence}:{result}",
    )


class EvaluationCreate(BaseModel):
    """Creation request for a Hypothesis Evaluation (content only).

    ``evidence_ids`` are the new observations/evidence used for this evaluation.
    ``observed_outcomes`` are the factual outcomes observed (structured).
    ``support_count`` and ``contradiction_count`` summarize how many predictions
    were satisfied vs contradicted.
    ``confidence_id`` references the Confidence calibration used in evaluation.
    ``result`` is the evaluation outcome: confirmed, falsified, or insufficient.
    ``rationale`` is a human-readable explanation of the evaluation reasoning.
    """

    tenant_id: uuid.UUID
    hypothesis_id: uuid.UUID
    evidence_ids: list[uuid.UUID] = Field(default_factory=list)
    observed_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    support_count: int = Field(ge=0, default=0)
    contradiction_count: int = Field(ge=0, default=0)
    confidence_id: uuid.UUID | None = None
    result: str
    rationale: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("result")
    @classmethod
    def _validate_result(cls, v: str) -> str:
        if v not in EVALUATION_RESULTS:
            valid = sorted(EVALUATION_RESULTS)
            raise ValueError(f"invalid result {v!r}, must be one of {valid}")  # noqa: TRY003
        return v

    model_config = ConfigDict(frozen=True)


class Evaluation(BaseModel):
    """Immutable Hypothesis Evaluation (Reasoning - Evaluate).

    Content is immutable (P1). The row always records which hypothesis was
    evaluated, what evidence was used, what was observed, how many predictions
    were supported/contradicted, the confidence reference, the result and the
    rationale. Multiple evaluations over time build an append-only history.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    hypothesis_id: uuid.UUID
    evidence_ids: list[uuid.UUID]
    observed_outcomes: list[dict[str, Any]]
    support_count: int
    contradiction_count: int
    confidence_id: uuid.UUID | None
    result: str
    rationale: str
    evaluated_at: datetime

    model_config = ConfigDict(frozen=True)


def build_evaluation(create: EvaluationCreate) -> Evaluation:
    """Materialize an Evaluation from a creation request (id assigned at creation)."""
    return Evaluation(
        id=evaluation_id(
            create.tenant_id,
            create.hypothesis_id,
            create.evidence_ids,
            create.result,
        ),
        tenant_id=create.tenant_id,
        hypothesis_id=create.hypothesis_id,
        evidence_ids=create.evidence_ids,
        observed_outcomes=create.observed_outcomes,
        support_count=create.support_count,
        contradiction_count=create.contradiction_count,
        confidence_id=create.confidence_id,
        result=create.result,
        rationale=create.rationale,
        evaluated_at=create.evaluated_at,
    )


def create_evaluation(  # noqa: PLR0913 - convenience wrapper for EvaluationCreate
    *,
    tenant_id: uuid.UUID,
    hypothesis_id: uuid.UUID,
    evidence_ids: list[uuid.UUID],
    observed_outcomes: list[dict[str, Any]],
    support_count: int,
    contradiction_count: int,
    confidence_id: uuid.UUID | None,
    result: str,
    rationale: str,
) -> Evaluation:
    """Convenience function to create an Evaluation directly (used by services)."""
    create = EvaluationCreate(
        tenant_id=tenant_id,
        hypothesis_id=hypothesis_id,
        evidence_ids=evidence_ids,
        observed_outcomes=observed_outcomes,
        support_count=support_count,
        contradiction_count=contradiction_count,
        confidence_id=confidence_id,
        result=result,
        rationale=rationale,
    )
    return build_evaluation(create)


INSERT_EVALUATION = text(
    """
    INSERT INTO hypothesis_evaluations (
        id, tenant_id, hypothesis_id, evidence_ids, observed_outcomes,
        support_count, contradiction_count, confidence_id, result, rationale, evaluated_at
    )
    VALUES (
        :id, :tenant_id, :hypothesis_id, :evidence_ids,
        CAST(:observed_outcomes AS jsonb), :support_count, :contradiction_count,
        :confidence_id, :result, :rationale, :evaluated_at
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, hypothesis_id, evidence_ids, observed_outcomes,
              support_count, contradiction_count, confidence_id, result, rationale, evaluated_at
    """
)

CHECK_EVALUATION_EXISTS = text("SELECT 1 FROM hypothesis_evaluations WHERE id = :id")

SELECT_EVALUATIONS = text(
    """
    SELECT id, tenant_id, hypothesis_id, evidence_ids, observed_outcomes,
           support_count, contradiction_count, confidence_id, result, rationale, evaluated_at
    FROM hypothesis_evaluations
    WHERE tenant_id = :tenant_id
    ORDER BY evaluated_at
    LIMIT :limit OFFSET :offset
    """
)

SELECT_EVALUATIONS_BY_HYPOTHESIS = text(
    """
    SELECT id, tenant_id, hypothesis_id, evidence_ids, observed_outcomes,
           support_count, contradiction_count, confidence_id, result, rationale, evaluated_at
    FROM hypothesis_evaluations
    WHERE tenant_id = :tenant_id AND hypothesis_id = :hypothesis_id
    ORDER BY evaluated_at
    """
)

SELECT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM hypothesis_evaluations")


class EvaluationStore:
    """Persistence gateway for the Evaluation Store (PostgreSQL hypothesis_evaluations)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_evaluation(self, evaluation: Evaluation) -> dict[str, Any] | None:
        """Insert one immutable evaluation row.

        Returns the persisted row, or None when it was already present
        (idempotent dedup by the deterministic content-addressed id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_EVALUATION,
                {
                    "id": evaluation.id,
                    "tenant_id": evaluation.tenant_id,
                    "hypothesis_id": evaluation.hypothesis_id,
                    "evidence_ids": list(evaluation.evidence_ids),
                    "observed_outcomes": json.dumps(
                        evaluation.observed_outcomes, default=str
                    ),
                    "support_count": evaluation.support_count,
                    "contradiction_count": evaluation.contradiction_count,
                    "confidence_id": evaluation.confidence_id,
                    "result": evaluation.result,
                    "rationale": evaluation.rationale,
                    "evaluated_at": evaluation.evaluated_at,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def evaluation_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating evaluations on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_EVALUATION_EXISTS, {"id": id})
            return result.scalar() is not None

    async def list_evaluations(
        self, *, tenant_id: uuid.UUID, limit: int = 500, offset: int = 0
    ) -> list[Evaluation]:
        """Read-only load of the immutable evaluation rows for a tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_EVALUATIONS, {"tenant_id": tenant_id, "limit": limit, "offset": offset}
            )
            rows = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["observed_outcomes"], str):
                    row["observed_outcomes"] = json.loads(row["observed_outcomes"])
                if isinstance(row["evidence_ids"], str):
                    row["evidence_ids"] = json.loads(row["evidence_ids"])
                rows.append(Evaluation(**row))
            return rows

    async def list_evaluations_by_hypothesis(
        self, *, tenant_id: uuid.UUID, hypothesis_id: uuid.UUID
    ) -> list[Evaluation]:
        """Read-only load of evaluations for a specific hypothesis."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_EVALUATIONS_BY_HYPOTHESIS,
                {"tenant_id": tenant_id, "hypothesis_id": hypothesis_id},
            )
            rows = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["observed_outcomes"], str):
                    row["observed_outcomes"] = json.loads(row["observed_outcomes"])
                if isinstance(row["evidence_ids"], str):
                    row["evidence_ids"] = json.loads(row["evidence_ids"])
                rows.append(Evaluation(**row))
            return rows

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Evaluation row."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()