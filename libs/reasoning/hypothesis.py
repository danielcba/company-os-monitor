"""Hypothesis model + append-only persistence (Reasoning - Predict).

P1: a Hypothesis is immutable once generated; it is only appended. All content
columns (anomaly_ids, pattern_ids, description, predicted_consequences,
falsification_criterion, coherence_score, generated_at) are assigned at
generation and never retrofitted; ``status`` is a lifecycle field
(candidate -> confirmed/falsified is decided later by future evidence and
Confidence, Sprint 8), so only ``status`` may change afterwards. The row is
never deleted (persistent audit trail; enforced by the content trigger).

The deterministic ``hypothesis_id`` includes the tenant, the anomalies and
patterns it accounts for AND the description text, so two different candidate
explanations over the same anomaly get distinct ids (competing hypotheses, per
the framework: premature convergence on a single explanation is a cognitive
failure) while re-generating the same hypothesis over the same facts produces
the same id (idempotent dedup by primary key). ``generated_at`` is deliberately
NOT part of the id: it would break idempotence between runs.
"""
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic hypothesis ids (content-addressed, idempotent).
HYPOTHESIS_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-00000000007f")

# Status lifecycle: a candidate is neither confirmed nor falsified in this
# phase. Confirmation/falsification requires future evidence + Confidence
# (Sprint 8) and is OUT of scope here.
STATUS_CANDIDATE = "candidate"
STATUS_CONFIRMED = "confirmed"
STATUS_FALSIFIED = "falsified"
HYPOTHESIS_STATUSES: frozenset[str] = frozenset(
    {STATUS_CANDIDATE, STATUS_CONFIRMED, STATUS_FALSIFIED}
)


def hypothesis_id(
    tenant_id: uuid.UUID,
    anomaly_ids: list[uuid.UUID],
    pattern_ids: list[uuid.UUID],
    description: str,
) -> uuid.UUID:
    """Derive a deterministic id from the hypothesis content.

    Anchors on the tenant, the anomalies/patterns it accounts for and the
    description text. Two distinct explanations of the same anomaly have
    distinct ids (competing hypotheses); re-generating the same explanation
    yields the same id (dedup by primary key). ``generated_at`` is excluded so
    re-runs stay idempotent.
    """
    ordered_anomalies = ",".join(str(x) for x in sorted(anomaly_ids))
    ordered_patterns = ",".join(str(x) for x in sorted(pattern_ids))
    return uuid.uuid5(
        HYPOTHESIS_NAMESPACE,
        f"{tenant_id}:{ordered_anomalies}:{ordered_patterns}:{description}",
    )


class HypothesisCreate(BaseModel):
    """Creation request for a generated Hypothesis (content only, no lifecycle).

    ``predicted_consequences`` are observable, falsifiable predictions and
    ``falsification_criterion`` is the concrete outcome that would demonstrate
    the hypothesis false - both REQUIRED (the framework pairs explanation with
    prediction; a prediction detached from explanation is not a hypothesis).
    ``coherence_score`` is a declarative estimate from the template library in
    the MVP; the calibrated coherence (S + C + ECE) arrives with Confidence
    (Sprint 8).
    """

    tenant_id: uuid.UUID
    anomaly_ids: list[uuid.UUID]
    pattern_ids: list[uuid.UUID] = Field(default_factory=list)
    description: str
    predicted_consequences: list[str]
    falsification_criterion: str
    coherence_score: float = Field(ge=0.0, le=1.0)
    status: str = STATUS_CANDIDATE
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Hypothesis(BaseModel):
    """Immutable generated Hypothesis (Reasoning - Predict).

    Content is immutable (P1); ``status`` is a lifecycle field. The row always
    records a testable explanation (``description``), its observable predicted
    consequences and the concrete ``falsification_criterion``. It is a
    tentative commitment - the system holds multiple competing hypotheses and
    neither confirms nor falsifies them in this phase.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    anomaly_ids: list[uuid.UUID]
    pattern_ids: list[uuid.UUID]
    description: str
    predicted_consequences: list[str]
    falsification_criterion: str
    coherence_score: float = Field(ge=0.0, le=1.0)
    status: str = STATUS_CANDIDATE
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


def build_hypothesis(create: HypothesisCreate) -> Hypothesis:
    """Materialize a Hypothesis from a creation request (id assigned at creation)."""
    return Hypothesis(
        id=hypothesis_id(
            create.tenant_id,
            create.anomaly_ids,
            create.pattern_ids,
            create.description,
        ),
        tenant_id=create.tenant_id,
        anomaly_ids=create.anomaly_ids,
        pattern_ids=create.pattern_ids,
        description=create.description,
        predicted_consequences=create.predicted_consequences,
        falsification_criterion=create.falsification_criterion,
        coherence_score=create.coherence_score,
        status=create.status,
        generated_at=create.generated_at,
    )


INSERT_HYPOTHESIS = text(
    """
    INSERT INTO hypotheses (
        id, tenant_id, anomaly_ids, pattern_ids, description,
        predicted_consequences, falsification_criterion, coherence_score,
        status, generated_at
    )
    VALUES (
        :id, :tenant_id, :anomaly_ids, :pattern_ids, :description,
        CAST(:predicted_consequences AS jsonb), :falsification_criterion,
        :coherence_score, :status, :generated_at
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, anomaly_ids, pattern_ids, description,
              falsification_criterion, coherence_score, status
    """
)

CHECK_HYPOTHESIS_EXISTS = text("SELECT 1 FROM hypotheses WHERE id = :id")

SELECT_HYPOTHESES = text(
    """
    SELECT id, tenant_id, anomaly_ids, pattern_ids, description,
           predicted_consequences, falsification_criterion, coherence_score,
           status, generated_at
    FROM hypotheses
    WHERE tenant_id = :tenant_id
    ORDER BY generated_at
    """
)

SELECT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM hypotheses")


class HypothesisStore:
    """Persistence gateway for the Hypothesis Store (PostgreSQL hypotheses table)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_hypothesis(self, hypothesis: Hypothesis) -> dict[str, Any] | None:
        """Insert one immutable hypothesis row.

        Returns the persisted row, or None when it was already present
        (idempotent dedup by deterministic id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_HYPOTHESIS,
                {
                    "id": hypothesis.id,
                    "tenant_id": hypothesis.tenant_id,
                    "anomaly_ids": list(hypothesis.anomaly_ids),
                    "pattern_ids": list(hypothesis.pattern_ids),
                    "description": hypothesis.description,
                    "predicted_consequences": json.dumps(
                        list(hypothesis.predicted_consequences)
                    ),
                    "falsification_criterion": hypothesis.falsification_criterion,
                    "coherence_score": hypothesis.coherence_score,
                    "status": hypothesis.status,
                    "generated_at": hypothesis.generated_at,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def hypothesis_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating hypotheses on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_HYPOTHESIS_EXISTS, {"id": id})
            return result.scalar() is not None

    async def list_hypotheses(self, *, tenant_id: uuid.UUID) -> list[Hypothesis]:
        """Read-only load of the immutable hypothesis rows for a tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_HYPOTHESES, {"tenant_id": tenant_id}
            )
            rows = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["predicted_consequences"], str):
                    row["predicted_consequences"] = json.loads(
                        row["predicted_consequences"]
                    )
                rows.append(Hypothesis(**row))
            return rows

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Hypothesis row."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()