"""Confidence READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the confidence_scores table (P1) for a single tenant (the token's
tenant scope is enforced in GatewayService/health.py). A Confidence row is the
calibrated reliability estimate (Learning · Calibrate) of a judgment under
evaluation (a Hypothesis in this phase; Recommendation/Decision in the Action
Layer): it records C_final (``confidence_score``), the first-class justification
(S(H|E), C(H), 1 - ECE, alpha, M, L0), the ECE and the calibration inputs that
made the score deterministic. This store pages, filters and sorts the
calibrated judgments and resolves the desglose for one row: the target judgment
under evaluation, resolved from the canonical table matching ``target_type``
(hypothesis -> the hypothesis with its anomalies/patterns/contexts; decision ->
the committed decision; recommendation -> the proposed recommendation). It
NEVER writes, never re-computes a score, never invents calibration data and
never reimplements the calibrator.

Content is fully immutable (P1, enforced by the content trigger on the table):
a re-calibration with different inputs is a NEW row (append-only history), never
an UPDATE; there is no lifecycle flag.
"""
import uuid
from typing import Any

from libs.shared.facets_cache import FacetsCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

TARGET_TYPES = ("hypothesis", "recommendation", "decision")

SELECT_BASE = """
    SELECT id, tenant_id, target_type, target_id, evidential_support,
           explanatory_coherence, historical_calibration, confidence_score,
           alpha, calibration_justification, calibration_error_estimate, computed_at
    FROM confidence_scores
    WHERE tenant_id = :tenant_id
      AND (CAST(:target_type AS VARCHAR) IS NULL OR target_type = :target_type)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM confidence_scores
    WHERE tenant_id = :tenant_id
      AND (CAST(:target_type AS VARCHAR) IS NULL OR target_type = :target_type)
"""

SORT_CLAUSES = {
    "computed_at_desc": "ORDER BY computed_at DESC, id",
    "computed_at_asc": "ORDER BY computed_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT target_type ORDER BY target_type), '[]')
         FROM (SELECT target_type FROM confidence_scores WHERE tenant_id = :tenant_id) t) AS target_types
    """
)

SUMMARY_SQL = text(
    """
    SELECT
      COUNT(*) AS total,
      COALESCE(AVG(confidence_score), 0) AS avg_confidence,
      COALESCE(AVG(evidential_support), 0) AS avg_support,
      COALESCE(AVG(explanatory_coherence), 0) AS avg_coherence,
      COALESCE(AVG(historical_calibration), 0) AS avg_historical_calibration,
      COALESCE(AVG(calibration_error_estimate), 0) AS avg_ece,
      COALESCE(AVG(alpha), 0) AS avg_alpha,
      COALESCE(MIN(confidence_score), 0) AS min_confidence,
      COALESCE(MAX(confidence_score), 0) AS max_confidence
    FROM confidence_scores
    WHERE tenant_id = :tenant_id
    """
)

SUMMARY_BY_TYPE_SQL = text(
    """
    SELECT target_type, COUNT(*) AS n
    FROM confidence_scores
    WHERE tenant_id = :tenant_id
    GROUP BY target_type
    ORDER BY target_type
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, target_type, target_id, evidential_support,
           explanatory_coherence, historical_calibration, confidence_score,
           alpha, calibration_justification, calibration_error_estimate, computed_at
    FROM confidence_scores
    WHERE tenant_id = :tenant_id AND id = :id
    """
)

SELECT_DECISION = text(
    """
    SELECT id, tenant_id, recommendation_id, confidence_id, authority_id,
           commitment, expected_outcomes, risk_tolerance, status, committed_at,
           executed_at, actual_outcomes
    FROM decisions
    WHERE tenant_id = :tenant_id AND id = :id
    """
)

SELECT_RECOMMENDATION = text(
    """
    SELECT id, tenant_id, hypothesis_id, insight_id, confidence_id,
           action_description, rationale, expected_consequences,
           alternatives_considered, confidence_score, status, proposed_at
    FROM recommendations
    WHERE tenant_id = :tenant_id AND id = :id
    """
)


class ConfidenceReadStore:
    """Persistence gateway for tenant-scoped, paginated confidence reads."""

    def __init__(self, dsn: str | None = None, engine: AsyncEngine | None = None, hypothesis_store=None):
        if engine is not None:
            self._engine = engine
        else:
            self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache = FacetsCache()
        self._hypothesis_store = hypothesis_store

    @staticmethod
    def _confidence_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable confidence row (the calibrated
        reliability estimate with its first-class justification - P5)."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "target_type": row["target_type"],
            "target_id": str(row["target_id"]),
            "evidential_support": float(row["evidential_support"]),
            "explanatory_coherence": float(row["explanatory_coherence"]),
            "historical_calibration": float(row["historical_calibration"]),
            "confidence_score": float(row["confidence_score"]),
            "alpha": float(row["alpha"]),
            "calibration_justification": row["calibration_justification"],
            "calibration_error_estimate": float(row["calibration_error_estimate"]),
            "computed_at": row["computed_at"].isoformat(),
        }

    async def list_confidence(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        target_type: str | None = None,
        sort: str = "computed_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the calibrated judgment stream."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["computed_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "target_type": target_type,
        }
        async with self._session_factory() as session:
            total = (
                await session.execute(text(COUNT_BASE), params)
            ).scalar_one()
            rows = await session.execute(
                text(f"{SELECT_BASE} {order_by} LIMIT :limit OFFSET :offset"),
                params,
            )
            confidence = [self._confidence_payload(row) for row in rows.mappings()]
            facets = await self._facets(session, tenant_id)
        return {
            "confidence": confidence,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_confidence(
        self, *, tenant_id: uuid.UUID, confidence_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One confidence row with its target desglose (the judgment under
        evaluation, resolved from the canonical table matching target_type)."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": confidence_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            confidence = self._confidence_payload(row)
            target = await self._resolve_target(
                session,
                tenant_id=tenant_id,
                target_type=row["target_type"],
                target_id=row["target_id"],
            )
        return {"confidence": confidence, "target": target}

    async def confidence_summary(
        self, *, tenant_id: uuid.UUID
    ) -> dict[str, Any]:
        """Pure READ aggregation over the tenant's calibrated judgments (the
        calibration state: how much of the pipeline has been calibrated and how
        the S / C / 1 - ECE / C_final spread looks). Factual only: it averages
        the persisted rows and never invents a pass/fail threshold (the concept
        leaves "Confidence thresholds for action" to a future version)."""
        async with self._session_factory() as session:
            agg = (
                await session.execute(SUMMARY_SQL, {"tenant_id": tenant_id})
            ).mappings().one()
            by_type = {
                row["target_type"]: int(row["n"])
                for row in (
                    await session.execute(
                        SUMMARY_BY_TYPE_SQL, {"tenant_id": tenant_id}
                    )
                ).mappings()
            }
        return {
            "total": int(agg["total"]),
            "by_target_type": by_type,
            "averages": {
                "confidence": float(agg["avg_confidence"]),
                "support": float(agg["avg_support"]),
                "coherence": float(agg["avg_coherence"]),
                "historical_calibration": float(agg["avg_historical_calibration"]),
                "ece": float(agg["avg_ece"]),
                "alpha": float(agg["avg_alpha"]),
            },
            "range": {
                "min_confidence": float(agg["min_confidence"]),
                "max_confidence": float(agg["max_confidence"]),
            },
        }

    async def _resolve_target(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Resolve the judgment under evaluation from its canonical table."""
        if target_type == "hypothesis" and self._hypothesis_store is not None:
            return await self._hypothesis_store.get_hypothesis(
                tenant_id=tenant_id, hypothesis_id=target_id
            )
        if target_type == "decision":
            row = (
                await session.execute(
                    SELECT_DECISION,
                    {"tenant_id": tenant_id, "id": target_id},
                )
            ).mappings().one_or_none()
            return self._decision_payload(row) if row is not None else None
        if target_type == "recommendation":
            row = (
                await session.execute(
                    SELECT_RECOMMENDATION,
                    {"tenant_id": tenant_id, "id": target_id},
                )
            ).mappings().one_or_none()
            return self._recommendation_payload(row) if row is not None else None
        return None

    @staticmethod
    def _decision_payload(row: Any) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "recommendation_id": str(row["recommendation_id"]),
            "confidence_id": str(row["confidence_id"]),
            "authority_id": str(row["authority_id"]),
            "commitment": row["commitment"],
            "risk_tolerance": row["risk_tolerance"],
            "status": row["status"],
            "committed_at": row["committed_at"].isoformat(),
        }

    @staticmethod
    def _recommendation_payload(row: Any) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "hypothesis_id": str(row["hypothesis_id"]),
            "confidence_id": str(row["confidence_id"]),
            "action_description": row["action_description"],
            "rationale": row["rationale"],
            "confidence_score": float(row["confidence_score"]),
            "status": row["status"],
            "proposed_at": row["proposed_at"].isoformat(),
        }

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct target types for the tenant (real values, not invented
        options) so the UI can offer honest filter choices."""
        cache_key = f"confidence:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "target_types": list(row["target_types"] or []),
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()