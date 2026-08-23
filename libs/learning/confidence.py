"""Confidence model + append-only persistence (Learning - Calibrate).

The Confidence concept (core-concepts/confidence.md) governs this module:
Confidence is a calibrated reliability estimate - computed, not intuited -
and it is the transversal capability that enables the Action Layer (R4:
no judgment that influences action without a confidence score and its reasons).

P1 enforcement: a ``confidence_scores`` row is immutable once written; it is
only appended. The deterministic ``confidence_id`` is content-addressed: it
hashes the tenant, the target and the calibration INPUTS (evidential support,
explanatory coherence, historical calibration, alpha) - deliberately EXCLUDING
``computed_at`` so re-calibrating the same judgment with identical inputs
produces the same id (idempotent dedup by primary key), while a NEW calibration
with different inputs (e.g. new evidence) yields a NEW row: the historical
calibration is preserved as an append-only audit trail (P1) instead of being
overwritten. ``get_confidence`` returns the most recent row for a target.

The row is never deleted; the content trigger blocks any UPDATE/DELETE (see
sprint8-confidence-content-trigger.sql and the base schema).
"""
import struct
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic confidence ids (content-addressed, idempotent).
CONFIDENCE_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000080")

# Target types the Calibrate capability can evaluate. The service calibrates
# ``hypothesis`` targets in this phase; ``recommendation``/``decision`` are
# calibrated by the Action Layer (Sprints 9/10) through the same API.
TARGET_TYPES: frozenset[str] = frozenset({"hypothesis", "recommendation", "decision"})


@dataclass(frozen=True)
class CalibrationContent:
    """The calibration inputs that determine the score (hashed into the id).

    ``evidential_support`` is S(H|E), ``explanatory_coherence`` is C(H),
    ``historical_calibration`` is 1 - ECE and ``alpha`` is the mixing
    coefficient. Together with the target they fully determine C_final, so they
    are the content that makes the confidence id deterministic and append-only.
    """

    evidential_support: float
    explanatory_coherence: float
    historical_calibration: float
    alpha: float


def _float_to_bytes(val: float) -> bytes:
    """Deterministic binary representation of a float for hashing.

    Uses IEEE 754 binary64 (big-endian) to avoid decimal formatting
    non-determinism (e.g. 0.7057850000000001 vs 0.705785).
    """
    return struct.pack("!d", val)


def confidence_id(
    tenant_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    content: CalibrationContent,
) -> uuid.UUID:
    """Derive a deterministic id from the calibration content.

    Anchors on the tenant, the target (``target_type`` + ``target_id``) and the
    calibration inputs that determine the score. Two calibrations of the same
    judgment with the SAME inputs yield the same id (idempotent dedup by primary
    key); a re-calibration with DIFFERENT inputs (new evidence, new coherence,
    different history) yields a DIFFERENT id - so the old row is never updated
    and the history is kept (append-only, P1). ``computed_at`` is deliberately
    excluded: it would break idempotence between runs.
    """
    parts = [
        str(tenant_id).encode(),
        target_type.encode(),
        str(target_id).encode(),
        _float_to_bytes(content.evidential_support),
        _float_to_bytes(content.explanatory_coherence),
        _float_to_bytes(content.historical_calibration),
        _float_to_bytes(content.alpha),
    ]
    return uuid.uuid5(CONFIDENCE_NAMESPACE, b":".join(parts))


class ConfidenceCreate(BaseModel):
    """Creation request for a calibrated Confidence (content only, no lifecycle).

    Fields mirror the ``confidence_scores`` table (docs/01). ``target_type`` is
    one of TARGET_TYPES; ``evidential_support`` is S(H|E), ``explanatory_coherence``
    is C(H), ``historical_calibration`` is 1 - ECE, ``confidence_score`` is
    C_final and ``calibration_error_estimate`` is the ECE of the judgment class.
    ``alpha`` is the fixed-a-priori mixing coefficient used in the computation.
    """

    tenant_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    evidential_support: float = Field(ge=0.0, le=1.0)
    explanatory_coherence: float = Field(ge=0.0, le=1.0)
    historical_calibration: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    alpha: float = Field(ge=0.0, le=1.0)
    calibration_justification: str
    calibration_error_estimate: float = Field(ge=0.0, le=1.0)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("target_type")
    @classmethod
    def _validate_target_type(cls, v: str) -> str:
        if v not in TARGET_TYPES:
            raise ValueError(f"target_type must be one of {sorted(TARGET_TYPES)}, got {v!r}")
        return v


class Confidence(BaseModel):
    """Immutable calibrated Confidence row (Learning - Calibrate).

    Content is immutable (P1): every field is assigned at calibration and never
    retrofitted; there is no lifecycle flag (a re-calibration with different
    inputs is a NEW row, never an UPDATE). The row always records the score
    (C_final), the reasons for it (``calibration_justification``) and the
    calibration error estimate (ECE), per the Confidence concept.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    evidential_support: float = Field(ge=0.0, le=1.0)
    explanatory_coherence: float = Field(ge=0.0, le=1.0)
    historical_calibration: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    alpha: float = Field(ge=0.0, le=1.0)
    calibration_justification: str
    calibration_error_estimate: float = Field(ge=0.0, le=1.0)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("target_type")
    @classmethod
    def _validate_target_type(cls, v: str) -> str:
        if v not in TARGET_TYPES:
            raise ValueError(f"target_type must be one of {sorted(TARGET_TYPES)}, got {v!r}")
        return v

    model_config = ConfigDict(frozen=True)


def build_confidence(create: ConfidenceCreate) -> Confidence:
    """Materialize a Confidence from a creation request (id assigned at creation).

    Note: computed_at is not included here - it will be set by the DB DEFAULT
    on insert and returned via RETURNING.
    """
    content = CalibrationContent(
        evidential_support=create.evidential_support,
        explanatory_coherence=create.explanatory_coherence,
        historical_calibration=create.historical_calibration,
        alpha=create.alpha,
    )
    return Confidence(
        id=confidence_id(
            create.tenant_id,
            create.target_type,
            create.target_id,
            content,
        ),
        tenant_id=create.tenant_id,
        target_type=create.target_type,
        target_id=create.target_id,
        evidential_support=create.evidential_support,
        explanatory_coherence=create.explanatory_coherence,
        historical_calibration=create.historical_calibration,
        confidence_score=create.confidence_score,
        alpha=create.alpha,
        calibration_justification=create.calibration_justification,
        calibration_error_estimate=create.calibration_error_estimate,
        computed_at=create.computed_at,  # placeholder; will be overwritten by DB value on insert
    )


INSERT_CONFIDENCE = text(
    """
    INSERT INTO confidence_scores (
        id, tenant_id, target_type, target_id, evidential_support,
        explanatory_coherence, historical_calibration, confidence_score,
        alpha, calibration_justification, calibration_error_estimate
    )
    VALUES (
        :id, :tenant_id, :target_type, :target_id, :evidential_support,
        :explanatory_coherence, :historical_calibration, :confidence_score,
        :alpha, :calibration_justification, :calibration_error_estimate
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, target_type, target_id, evidential_support,
              explanatory_coherence, historical_calibration, confidence_score,
              alpha, calibration_justification, calibration_error_estimate, computed_at
    """
)

CHECK_CONFIDENCE_EXISTS = text("SELECT 1 FROM confidence_scores WHERE id = :id")

SELECT_CONFIDENCE = text(
    """
    SELECT id, tenant_id, target_type, target_id, evidential_support,
           explanatory_coherence, historical_calibration, confidence_score,
           alpha, calibration_justification, calibration_error_estimate, computed_at
    FROM confidence_scores
    WHERE tenant_id = :tenant_id
    ORDER BY computed_at, id
    """
)

SELECT_LATEST_BY_TARGET = text(
    """
    SELECT id, tenant_id, target_type, target_id, evidential_support,
           explanatory_coherence, historical_calibration, confidence_score,
           alpha, calibration_justification, calibration_error_estimate, computed_at
    FROM confidence_scores
    WHERE target_type = :target_type AND target_id = :target_id
    ORDER BY computed_at DESC, id DESC
    LIMIT 1
    """
)

SELECT_TENANT_IDS = text("SELECT DISTINCT tenant_id FROM confidence_scores")


class ConfidenceStore:
    """Persistence gateway for the Confidence Store (PostgreSQL confidence_scores)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_confidence(self, confidence: Confidence) -> dict[str, Any] | None:
        """Insert one immutable confidence row.

        Returns the persisted row (with DB-generated computed_at), or None when
        it was already present (idempotent dedup by the deterministic
        content-addressed id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_CONFIDENCE,
                {
                    "id": confidence.id,
                    "tenant_id": confidence.tenant_id,
                    "target_type": confidence.target_type,
                    "target_id": confidence.target_id,
                    "evidential_support": confidence.evidential_support,
                    "explanatory_coherence": confidence.explanatory_coherence,
                    "historical_calibration": confidence.historical_calibration,
                    "confidence_score": confidence.confidence_score,
                    "alpha": confidence.alpha,
                    "calibration_justification": confidence.calibration_justification,
                    "calibration_error_estimate": confidence.calibration_error_estimate,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def confidence_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating confidence on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_CONFIDENCE_EXISTS, {"id": id})
            return result.scalar() is not None

    async def list_confidence(
        self, *, tenant_id: uuid.UUID, limit: int = 500, offset: int = 0
    ) -> list[Confidence]:
        """Read-only load of the immutable confidence rows for a tenant.

        Supports pagination via ``limit`` and ``offset`` to avoid loading
        all confidence rows into memory for tenants with large datasets.
        """
        sql = SELECT_CONFIDENCE + text(" LIMIT :limit OFFSET :offset")
        async with self._session_factory() as session:
            result = await session.execute(
                sql, {"tenant_id": tenant_id, "limit": limit, "offset": offset}
            )
            return [Confidence(**dict(row)) for row in result.mappings()]

    async def get_confidence(
        self, *, target_type: str, target_id: uuid.UUID
    ) -> Confidence | None:
        """The most recent calibration row for one target (append-only history).

        A target may have several rows (each a distinct calibration with
        different inputs); this returns the latest by ``computed_at``.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_LATEST_BY_TARGET,
                {"target_type": target_type, "target_id": target_id},
            )
            row = result.mappings().one_or_none()
            return Confidence(**dict(row)) if row is not None else None

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Confidence row."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_IDS)
            return [row[0] for row in result.all()]

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()