"""Decision model + append-only persistence (Action - Commit).

The Decision concept (core-concepts/decision.md) governs this module: a Decision
is a commitment to a course of action, selected from available alternatives,
based on the current understanding and its confidence. "A decision ends
deliberation. It does not end learning." The Commitment capability converts
understanding into committed action and creates the conditions for
accountability (P6: a Recommendation is advisory and reversible; commitment and
authority belong here).

Falsifiability (Popper): "Its expected outcomes must be stated in observable,
verifiable terms before the decision is executed." and "This rule converts every
decision from an act of authority into an experiment." Every Decision row stores
``expected_outcomes`` (a list of ``{"prediction", "verifiable_by", "deadline"}``)
declared BEFORE execution; the comparison expected vs actual is the primary
learning signal of the Learning loop (P7, future sprints).

P1 enforcement: a ``decisions`` row is append-only. The deterministic
``decision_id`` is content-addressed: it anchors on the tenant, the specific
Recommendation being committed and its specific calibrated Confidence row,
deliberately EXCLUDING ``committed_at`` so re-committing the SAME offer over the
SAME inputs produces the same id (idempotent dedup by primary key). The row is
never deleted and its content columns are immutable (blocked by the content
trigger); ``status`` is a lifecycle field
(committed -> executing/completed/rolled_back) and ``executed_at``/
``actual_outcomes`` are lifecycle fields populated only by the Learning loop
(future sprints). In this MVP the Decision is RECORDED, never executed (P6): no
real-world action happens and ``executed_at``/``actual_outcomes`` stay NULL.
"""
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic decision ids (content-addressed, idempotent).
DECISION_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000082")

# Lifecycle of the commitment: status is a lifecycle field (content is
# immutable, P1). A decision starts ``committed`` and is later executed or
# rolled back by the Learning loop / execution phases (future sprints).
STATUS_COMMITTED = "committed"
STATUS_EXECUTING = "executing"
STATUS_COMPLETED = "completed"
STATUS_ROLLED_BACK = "rolled_back"
DECISION_STATUSES: frozenset[str] = frozenset(
    {STATUS_COMMITTED, STATUS_EXECUTING, STATUS_COMPLETED, STATUS_ROLLED_BACK}
)

# Declared risk tolerance levels (docs/03: "> 0.75 to commit; > 0.9 for
# irreversible"). The Committer maps Confidence -> risk tolerance against the
# Decision Policy (procedural memory, libs/procedural_memory/decision_policy.py).
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_TOLERANCES: frozenset[str] = frozenset({RISK_LOW, RISK_MEDIUM, RISK_HIGH})

# Required keys of every falsifiable expected outcome (docs/04 Decision Schema).
OUTCOME_PREDICTION = "prediction"
OUTCOME_VERIFIABLE_BY = "verifiable_by"
OUTCOME_DEADLINE = "deadline"
EXPECTED_OUTCOME_KEYS: frozenset[str] = frozenset(
    {OUTCOME_PREDICTION, OUTCOME_VERIFIABLE_BY, OUTCOME_DEADLINE}
)


def decision_id(
    tenant_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    confidence_id: uuid.UUID,
) -> uuid.UUID:
    """Derive a deterministic id from the decision content.

    Anchors on the tenant, the specific Recommendation being committed and the
    specific calibrated Confidence row that supports it. Re-committing the SAME
    offer over the SAME inputs yields the same id (dedup by primary key).
    ``committed_at`` is deliberately excluded: it would break idempotence
    between runs. In the MVP the commitment is derived deterministically from
    the Recommendation + Confidence + Policy, so a re-run over the same inputs
    never duplicates the Decision (append-only, P1).
    """
    return uuid.uuid5(
        DECISION_NAMESPACE,
        f"{tenant_id}:{recommendation_id}:{confidence_id}",
    )


class DecisionCreate(BaseModel):
    """Creation request for a committed Decision (content + declared lifecycle).

    Fields mirror the ``decisions`` table (docs/01, docs/04). ``commitment`` is
    a DEFINITIVE statement of the selected course of action (the concept: "A
    decision is a commitment with an owner, a timeline, and expected outcomes";
    a vague intention is a Non-example). ``expected_outcomes`` is a list of
    falsifiable predictions in observable, verifiable terms - each MUST carry
    ``prediction``, ``verifiable_by`` and ``deadline`` (R5 / Decision spec).
    ``authority_id`` references the commitment authority (a user or a policy);
    ``risk_tolerance`` is the declared level (low/medium/high); ``status``
    defaults to ``committed`` (P6: recorded, never executed in this MVP).
    """

    tenant_id: uuid.UUID
    recommendation_id: uuid.UUID
    confidence_id: uuid.UUID
    authority_id: uuid.UUID
    commitment: str
    expected_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    risk_tolerance: str = RISK_LOW
    status: str = STATUS_COMMITTED
    committed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    executed_at: datetime | None = None
    actual_outcomes: list[dict[str, Any]] | None = None

    model_config = ConfigDict(frozen=True)


class Decision(BaseModel):
    """Immutable committed Decision row (Action - Commit).

    Content is immutable (P1); ``status``, ``executed_at`` and
    ``actual_outcomes`` are lifecycle fields: the Learning loop (future
    sprints) transitions committed -> executing/completed/rolled_back and
    records the observed outcomes for the expected vs actual comparison. The
    row always records the definitive ``commitment``, the falsifiable
    ``expected_outcomes`` (prediction + verifiable_by + deadline), the
    ``authority_id`` under which it was taken and the calibrated Confidence
    that supported it (R4).
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    recommendation_id: uuid.UUID
    confidence_id: uuid.UUID
    authority_id: uuid.UUID
    commitment: str
    expected_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    risk_tolerance: str = RISK_LOW
    status: str = STATUS_COMMITTED
    committed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    executed_at: datetime | None = None
    actual_outcomes: list[dict[str, Any]] | None = None

    model_config = ConfigDict(frozen=True)


def build_decision(create: DecisionCreate) -> Decision:
    """Materialize a Decision from a creation request (id at creation)."""
    return Decision(
        id=decision_id(
            create.tenant_id,
            create.recommendation_id,
            create.confidence_id,
        ),
        tenant_id=create.tenant_id,
        recommendation_id=create.recommendation_id,
        confidence_id=create.confidence_id,
        authority_id=create.authority_id,
        commitment=create.commitment,
        expected_outcomes=create.expected_outcomes,
        risk_tolerance=create.risk_tolerance,
        status=create.status,
        committed_at=create.committed_at,
        executed_at=create.executed_at,
        actual_outcomes=create.actual_outcomes,
    )


INSERT_DECISION = text(
    """
    INSERT INTO decisions (
        id, tenant_id, recommendation_id, confidence_id, authority_id,
        commitment, expected_outcomes, risk_tolerance, status, committed_at,
        executed_at, actual_outcomes
    )
    VALUES (
        :id, :tenant_id, :recommendation_id, :confidence_id, :authority_id,
        :commitment, CAST(:expected_outcomes AS jsonb), :risk_tolerance,
        :status, :committed_at, :executed_at, CAST(:actual_outcomes AS jsonb)
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, recommendation_id, confidence_id, authority_id,
              commitment, risk_tolerance, status, committed_at
    """
)

CHECK_DECISION_EXISTS = text("SELECT 1 FROM decisions WHERE id = :id")

SELECT_DECISIONS = text(
    """
    SELECT id, tenant_id, recommendation_id, confidence_id, authority_id,
           commitment, expected_outcomes, risk_tolerance, status, committed_at,
           executed_at, actual_outcomes
    FROM decisions
    WHERE tenant_id = :tenant_id
    ORDER BY committed_at, id
    """
)

SELECT_DECISIONS_BY_STATUS = text(
    """
    SELECT id, tenant_id, recommendation_id, confidence_id, authority_id,
           commitment, expected_outcomes, risk_tolerance, status, committed_at,
           executed_at, actual_outcomes
    FROM decisions
    WHERE tenant_id = :tenant_id AND status = :status
    ORDER BY committed_at, id
    """
)

SELECT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM decisions")


class DecisionStore:
    """Persistence gateway for the Decision Store (PostgreSQL decisions)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_decision(self, decision: Decision) -> dict[str, Any] | None:
        """Insert one immutable decision row (append-only, P1).

        Returns the persisted row, or None when it was already present
        (idempotent dedup by the deterministic content-addressed id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_DECISION,
                {
                    "id": decision.id,
                    "tenant_id": decision.tenant_id,
                    "recommendation_id": decision.recommendation_id,
                    "confidence_id": decision.confidence_id,
                    "authority_id": decision.authority_id,
                    "commitment": decision.commitment,
                    "expected_outcomes": json.dumps(
                        decision.expected_outcomes, default=str
                    ),
                    "risk_tolerance": decision.risk_tolerance,
                    "status": decision.status,
                    "committed_at": decision.committed_at,
                    "executed_at": decision.executed_at,
                    "actual_outcomes": (
                        json.dumps(decision.actual_outcomes, default=str)
                        if decision.actual_outcomes is not None
                        else None
                    ),
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def decision_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating decisions on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_DECISION_EXISTS, {"id": id})
            return result.scalar() is not None

    async def list_decisions(self, *, tenant_id: uuid.UUID) -> list[Decision]:
        """Read-only load of the immutable decision rows for a tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_DECISIONS, {"tenant_id": tenant_id}
            )
            return [self._row_to_decision(row) for row in result.mappings()]

    async def list_decisions_by_status(
        self, *, tenant_id: uuid.UUID, status: str
    ) -> list[Decision]:
        """Read-only load of decisions for a tenant filtered by lifecycle status.

        Exposed for the Learning loop (expected vs actual comparison over the
        committed/completed decisions) and for the Report service (Sprint 11).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_DECISIONS_BY_STATUS,
                {"tenant_id": tenant_id, "status": status},
            )
            return [self._row_to_decision(row) for row in result.mappings()]

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Decision row."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _row_to_decision(mapping) -> Decision:
        row = dict(mapping)
        if isinstance(row["expected_outcomes"], str):
            row["expected_outcomes"] = json.loads(row["expected_outcomes"])
        if isinstance(row["actual_outcomes"], str):
            row["actual_outcomes"] = json.loads(row["actual_outcomes"])
        return Decision(**row)