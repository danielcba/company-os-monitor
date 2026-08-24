"""Recommendation READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the recommendations table (P1) for a single tenant (the token's
tenant scope is enforced in GatewayService/health.py). A Recommendation is a
proposed course of action (Action · Propose): an offer, never a commitment (P6)
— it carries the action description, the traceable rationale, the expected
observable consequences, the alternatives considered and the CALIBRATED
confidence_score of the leading Hypothesis (R4: the recommendation never
recalibrates; it carries the score and its reasons, already computed by the
calibrator). Content is immutable (P1, enforced by the content trigger): only
``status`` is a lifecycle field (proposed -> accepted/rejected/superseded,
decided by the Decision layer). This store pages, filters and sorts the offers
and resolves the desglose for one row: the leading Hypothesis (with its
anomalies/patterns/contexts) and the specific calibrated Confidence row that
supports the offer. It NEVER writes, never executes actions and never
reimplements the formulator.
"""
import json
import uuid
from typing import Any

from libs.shared.facets_cache import FacetsCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

RECOMMENDATION_STATUSES = ("proposed", "accepted", "rejected", "superseded")

SELECT_BASE = """
    SELECT id, tenant_id, hypothesis_id, insight_id, confidence_id,
           action_description, rationale, expected_consequences,
           alternatives_considered, confidence_score, status, proposed_at
    FROM recommendations
    WHERE tenant_id = :tenant_id
      AND (CAST(:status AS VARCHAR) IS NULL OR status = :status)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM recommendations
    WHERE tenant_id = :tenant_id
      AND (CAST(:status AS VARCHAR) IS NULL OR status = :status)
"""

SORT_CLAUSES = {
    "proposed_at_desc": "ORDER BY proposed_at DESC, id",
    "proposed_at_asc": "ORDER BY proposed_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT status ORDER BY status), '[]')
         FROM (SELECT status FROM recommendations WHERE tenant_id = :tenant_id) t) AS statuses
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, hypothesis_id, insight_id, confidence_id,
           action_description, rationale, expected_consequences,
           alternatives_considered, confidence_score, status, proposed_at
    FROM recommendations
    WHERE tenant_id = :tenant_id AND id = :id
    """
)


class RecommendationReadStore:
    """Persistence gateway for tenant-scoped, paginated recommendation reads."""

    def __init__(self, dsn: str | None = None, engine: AsyncEngine | None = None, hypothesis_store=None, confidence_store=None):
        if engine is not None:
            self._engine = engine
        else:
            self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache = FacetsCache()
        self._hypothesis_store = hypothesis_store
        self._confidence_store = confidence_store

    @staticmethod
    def _recommendation_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable recommendation row (the offer
        with its rationale, expected consequences, alternatives and calibrated
        confidence - P6: advisory and reversible, never executed here)."""
        expected_consequences = row["expected_consequences"]
        if isinstance(expected_consequences, str):
            expected_consequences = json.loads(expected_consequences)
        alternatives = row["alternatives_considered"]
        if isinstance(alternatives, str):
            alternatives = json.loads(alternatives)
        payload = {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "hypothesis_id": str(row["hypothesis_id"]),
            "confidence_id": str(row["confidence_id"]),
            "action_description": row["action_description"],
            "rationale": row["rationale"],
            "expected_consequences": list(expected_consequences or []),
            "alternatives_considered": list(alternatives or []),
            "confidence_score": float(row["confidence_score"]),
            "status": row["status"],
            "proposed_at": row["proposed_at"].isoformat(),
        }
        if row["insight_id"] is not None:
            payload["insight_id"] = str(row["insight_id"])
        return payload

    async def list_recommendations(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        sort: str = "proposed_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the proposed action offers."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["proposed_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "status": status,
        }
        async with self._session_factory() as session:
            total = (
                await session.execute(text(COUNT_BASE), params)
            ).scalar_one()
            rows = await session.execute(
                text(f"{SELECT_BASE} {order_by} LIMIT :limit OFFSET :offset"),
                params,
            )
            recommendations = [
                self._recommendation_payload(row) for row in rows.mappings()
            ]
            facets = await self._facets(session, tenant_id)
        return {
            "recommendations": recommendations,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_recommendation(
        self, *, tenant_id: uuid.UUID, recommendation_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One recommendation with its desglose: the leading Hypothesis (with
        its anomalies/patterns/contexts) and the calibrated Confidence row that
        supports the offer (with its own target desglose)."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": recommendation_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            recommendation = self._recommendation_payload(row)
            hypothesis = None
            if self._hypothesis_store is not None:
                hypothesis = await self._hypothesis_store.get_hypothesis(
                    tenant_id=tenant_id, hypothesis_id=row["hypothesis_id"]
                )
            confidence = None
            if self._confidence_store is not None:
                confidence = await self._confidence_store.get_confidence(
                    tenant_id=tenant_id, confidence_id=row["confidence_id"]
                )
        return {
            "recommendation": recommendation,
            "hypothesis": hypothesis,
            "confidence": confidence,
        }

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct statuses for the tenant (real values, not invented options)
        so the UI can offer honest filter choices."""
        cache_key = f"recommendations:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "statuses": list(row["statuses"] or []),
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()