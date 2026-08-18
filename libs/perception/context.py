"""Context model + append-only persistence (Perception - Explain).

P2: Context is never generated directly - it is activated by explanatory
coherence competition among compatible mental models. This module provides:

* ``MentalModel`` - a declarative (non-reasoning) definition of what a model
  explains, for which purposes it is relevant, and its explanatory scope.
* ``Context`` (pydantic frozen) - the Active Context selected for a purpose.
* ``ContextStore`` - append-only persistence over the ``contexts`` table.

P1 vs lifecycle: the content columns (evidence_ids, mental_model_id, purpose,
coherence_score, competing_models) are immutable once activated; ``is_active``
is a lifecycle flag so an older context of the same purpose can be superseded
by a new activation (see the content trigger in the schema).
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic context ids (content-addressed, idempotent).
CONTEXT_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-00000000007c")

# Canonical purpose strings used to group competing mental models.
PURPOSE_INFRASTRUCTURE_HEALTH = "infrastructure_health"
PURPOSE_SECURITY_POSTURE = "security_posture"
PURPOSE_CAPACITY_MANAGEMENT = "capacity_management"
PURPOSES: frozenset[str] = frozenset(
    {
        PURPOSE_INFRASTRUCTURE_HEALTH,
        PURPOSE_SECURITY_POSTURE,
        PURPOSE_CAPACITY_MANAGEMENT,
    }
)


@dataclass(frozen=True)
class MentalModel:
    """Declarative definition of a candidate interpretation (never reasoning).

    ``explains`` maps to the evidence ``organization_type`` values produced by
    the Evidence Organizer (Sprint 3). ``purposes`` narrows in which purposes
    the model competes. Coherence is later computed from this declarative
    signature plus the available evidence weights - never invented here.
    """

    model_id: str
    explains: frozenset[str] = field(default_factory=frozenset)
    purposes: frozenset[str] = field(default_factory=frozenset)
    description: str = ""


MENTAL_MODEL_CATALOG: tuple[MentalModel, ...] = (
    MentalModel(
        model_id="resource_pressure",
        explains=frozenset({"resource_exhaustion_evidence"}),
        purposes=frozenset({PURPOSE_INFRASTRUCTURE_HEALTH, PURPOSE_CAPACITY_MANAGEMENT}),
        description=(
            "Explains evidence of concurrently exhausted cpu/memory/disk "
            "resources on a host (resource_exhaustion_evidence)."
        ),
    ),
    MentalModel(
        model_id="service_failure",
        explains=frozenset({"service_degradation_evidence"}),
        purposes=frozenset({PURPOSE_INFRASTRUCTURE_HEALTH, PURPOSE_SECURITY_POSTURE}),
        description=(
            "Explains evidence of a configured service stopped while an error "
            "event is recorded (service_degradation_evidence)."
        ),
    ),
    MentalModel(
        model_id="auth_compromise",
        explains=frozenset({"auth_anomaly_evidence"}),
        purposes=frozenset({PURPOSE_SECURITY_POSTURE}),
        description=(
            "Explains evidence of an account lockout coinciding with a "
            "privileged group membership change (auth_anomaly_evidence)."
        ),
    ),
    MentalModel(
        model_id="capacity_risk",
        explains=frozenset({"backup_failure_evidence", "vmware_capacity_evidence"}),
        purposes=frozenset({PURPOSE_INFRASTRUCTURE_HEALTH, PURPOSE_CAPACITY_MANAGEMENT}),
        description=(
            "Explains evidence of storage/backup capacity in shortfall "
            "(backup_failure_evidence, vmware_capacity_evidence)."
        ),
    ),
    MentalModel(
        model_id="connectivity_degradation",
        explains=frozenset({"network_anomaly_evidence"}),
        purposes=frozenset({PURPOSE_INFRASTRUCTURE_HEALTH}),
        description=(
            "Explains evidence of interface error rates with port state "
            "changes (network_anomaly_evidence)."
        ),
    ),
)

MENTAL_MODELS: dict[str, MentalModel] = {m.model_id: m for m in MENTAL_MODEL_CATALOG}


def models_for_purpose(purpose: str) -> list[MentalModel]:
    """All candidate mental models that compete for a given purpose."""
    return [m for m in MENTAL_MODEL_CATALOG if purpose in m.purposes]


def context_id(
    tenant_id: uuid.UUID, purpose: str, evidence_ids: list[uuid.UUID]
) -> uuid.UUID:
    """Derive a deterministic id from the context content.

    Re-activating the same context over the same evidence for the same purpose
    yields the same id, which makes re-runs idempotent (dedup by primary key).
    """
    ordered = ",".join(str(x) for x in sorted(evidence_ids))
    return uuid.uuid5(CONTEXT_NAMESPACE, f"{tenant_id}:{purpose}:{ordered}")


class ContextCreate(BaseModel):
    """Creation request for an Active Context (content only, no lifecycle)."""

    tenant_id: uuid.UUID
    evidence_ids: list[uuid.UUID]
    mental_model_id: str
    purpose: str
    coherence_score: float = Field(ge=0.0, le=1.0)
    competing_models: list[dict[str, Any]] = Field(default_factory=list)


class Context(BaseModel):
    """Immutable Active Context (Perception - Explain).

    Content columns are immutable (P1); ``is_active`` is a lifecycle flag. The
    row always records why a model won (``coherence_score``) and against which
    alternatives (``competing_models``) so the competition stays auditable (P2).
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    evidence_ids: list[uuid.UUID]
    mental_model_id: str
    purpose: str
    coherence_score: float = Field(ge=0.0, le=1.0)
    competing_models: list[dict[str, Any]] = Field(default_factory=list)
    activated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True

    model_config = ConfigDict(frozen=True)


def build_context(create: ContextCreate) -> Context:
    """Materialize a Context from a creation request (id assigned at creation)."""
    return Context(
        id=context_id(create.tenant_id, create.purpose, create.evidence_ids),
        tenant_id=create.tenant_id,
        evidence_ids=create.evidence_ids,
        mental_model_id=create.mental_model_id,
        purpose=create.purpose,
        coherence_score=create.coherence_score,
        competing_models=create.competing_models,
    )


INSERT_CONTEXT = text(
    """
    INSERT INTO contexts (
        id, tenant_id, evidence_ids, mental_model_id, purpose,
        coherence_score, competing_models, activated_at, is_active
    )
    VALUES (
        :id, :tenant_id, :evidence_ids, :mental_model_id, :purpose,
        :coherence_score, CAST(:competing_models AS jsonb), :activated_at, :is_active
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, mental_model_id, purpose, coherence_score, is_active
    """
)

DEACTIVATE_CONTEXT = text(
    """
    UPDATE contexts
    SET is_active = false
    WHERE tenant_id = :tenant_id
      AND purpose = :purpose
      AND is_active = true
      AND id <> :exclude_id
    """
)

SET_CONTEXT_ACTIVE = text(
    "UPDATE contexts SET is_active = :is_active WHERE id = :id"
)

CHECK_CONTEXT_EXISTS = text("SELECT 1 FROM contexts WHERE id = :id")

SELECT_CONTEXTS = text(
    """
    SELECT id, tenant_id, evidence_ids, mental_model_id, purpose,
           coherence_score, competing_models, activated_at, is_active
    FROM contexts
    WHERE tenant_id = :tenant_id
    ORDER BY activated_at
    """
)

SELECT_ACTIVE_CONTEXTS = text(
    """
    SELECT id, tenant_id, evidence_ids, mental_model_id, purpose,
           coherence_score, competing_models, activated_at, is_active
    FROM contexts
    WHERE tenant_id = :tenant_id
      AND is_active = true
    ORDER BY activated_at
    """
)

SELECT_CONTEXT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM contexts")


class ContextStore:
    """Persistence gateway for the Context Store (PostgreSQL contexts table)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_context(self, context: Context) -> dict[str, Any] | None:
        """Insert one immutable context row and supervise the activation cycle.

        Returns the persisted row, or None when it was already present
        (idempotent dedup). Only a newly inserted activation supersedes the
        previous active context of the same tenant+purpose (is_active lifecycle).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_CONTEXT,
                {
                    "id": context.id,
                    "tenant_id": context.tenant_id,
                    "evidence_ids": list(context.evidence_ids),
                    "mental_model_id": context.mental_model_id,
                    "purpose": context.purpose,
                    "coherence_score": context.coherence_score,
                    "competing_models": json.dumps(context.competing_models, default=str),
                    "activated_at": context.activated_at,
                    "is_active": context.is_active,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            if row is not None:
                await session.execute(
                    DEACTIVATE_CONTEXT,
                    {
                        "tenant_id": context.tenant_id,
                        "purpose": context.purpose,
                        "exclude_id": context.id,
                    },
                )
                await session.commit()
            return dict(row) if row is not None else None

    async def set_active(self, *, id: uuid.UUID, is_active: bool) -> None:
        """Flip the lifecycle flag of one context (content columns untouched)."""
        async with self._session_factory() as session:
            await session.execute(
                SET_CONTEXT_ACTIVE, {"id": id, "is_active": is_active}
            )
            await session.commit()

    async def context_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating contexts on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_CONTEXT_EXISTS, {"id": id})
            return result.scalar() is not None

    async def list_contexts(self, *, tenant_id: uuid.UUID) -> list[Context]:
        """Read-only load of the full Context stream for a tenant.

        Returns ALL activations ordered by ``activated_at`` - the continuous
        stream of Context, not only the current ``is_active = true`` ones. The
        Pattern Detector (Reasoning) reads this knowledge stream and never
        modifies contexts (P1).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_CONTEXTS, {"tenant_id": tenant_id}
            )
            rows = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["competing_models"], str):
                    row["competing_models"] = json.loads(row["competing_models"])
                rows.append(Context(**row))
            return rows

    async def list_active_contexts(self, *, tenant_id: uuid.UUID) -> list[Context]:
        """Read-only load of the current Active Contexts (``is_active = true``).

        Returns the current activation per tenant+purpose - the subjects the
        Anomaly Detector (Reasoning) compares against their expected Pattern.
        Content stays untouched (P1); only reads.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_ACTIVE_CONTEXTS, {"tenant_id": tenant_id}
            )
            rows = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["competing_models"], str):
                    row["competing_models"] = json.loads(row["competing_models"])
                rows.append(Context(**row))
            return rows

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Context row (detector inputs)."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_CONTEXT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()