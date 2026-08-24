"""Insight READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the insights table (P1) for a single tenant (the token's tenant
scope is enforced in GatewayService/health.py). An Insight is a novel
understanding that results from RESTRUCTURING the relationship between existing
knowledge elements - it is not new information, it is a new organization of
information that was already available (Reasoning · Restructure). This store
pages, filters and sorts the immutable insight rows and resolves the desglose
for one insight: the hypotheses it restructures (from the canonical hypotheses
table by ``hypothesis_ids``) and the Active Context it operates on (from the
canonical contexts table by ``context_id``). It NEVER writes, never invents
explanations, and never reimplements the generator.

Content is immutable (P1) and there is no lifecycle status: an Insight is a
journaled transformation, never updated and never deleted. The row always
records the Active Context, the restructured Hypotheses, the new organization
(``description``), what was understood before (``prior_understanding``) and the
declarative ``mental_model_update``.
"""
import uuid
from typing import Any

from libs.shared.facets_cache import FacetsCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.contexts import ContextReadStore
from src.hypotheses import HypothesisReadStore

SELECT_BASE = """
    SELECT id, tenant_id, context_id, hypothesis_ids, description,
           prior_understanding, mental_model_update, generated_at
    FROM insights
    WHERE tenant_id = :tenant_id
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM insights
    WHERE tenant_id = :tenant_id
"""

SORT_CLAUSES = {
    "generated_at_desc": "ORDER BY generated_at DESC, id",
    "generated_at_asc": "ORDER BY generated_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT hyp_id ORDER BY hyp_id), '[]')
         FROM (SELECT unnest(hypothesis_ids) AS hyp_id
               FROM insights WHERE tenant_id = :tenant_id) t) AS hypothesis_ids,
      (SELECT COALESCE(jsonb_agg(DISTINCT context_id ORDER BY context_id), '[]')
         FROM (SELECT context_id FROM insights WHERE tenant_id = :tenant_id) t) AS context_ids
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, context_id, hypothesis_ids, description,
           prior_understanding, mental_model_update, generated_at
    FROM insights
    WHERE tenant_id = :tenant_id AND id = :id
    """
)

SELECT_HYPOTHESES = text(
    """
    SELECT id, tenant_id, anomaly_ids, pattern_ids, description,
           predicted_consequences, falsification_criterion, coherence_score,
           status, generated_at
    FROM hypotheses
    WHERE tenant_id = :tenant_id AND id = ANY(:hypothesis_ids)
    """
)

SELECT_CONTEXT = text(
    """
    SELECT id, tenant_id, evidence_ids, mental_model_id, purpose,
           coherence_score, competing_models, activated_at, is_active
    FROM contexts
    WHERE tenant_id = :tenant_id AND id = :context_id
    """
)


class InsightReadStore:
    """Persistence gateway for tenant-scoped, paginated insight reads."""

    def __init__(self, dsn: str | None = None, engine: AsyncEngine | None = None):
        if engine is not None:
            self._engine = engine
        else:
            self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache = FacetsCache()

    @staticmethod
    def _insight_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable insight row (a journaled
        transformation that restructures existing knowledge elements)."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "context_id": str(row["context_id"]),
            "hypothesis_ids": [str(x) for x in (row["hypothesis_ids"] or [])],
            "description": row["description"],
            "prior_understanding": row["prior_understanding"],
            "mental_model_update": row["mental_model_update"],
            "generated_at": row["generated_at"].isoformat(),
        }

    async def list_insights(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        sort: str = "generated_at_desc",
    ) -> dict[str, Any]:
        """Paginated, sortable read of the immutable insight stream."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["generated_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
        }
        async with self._session_factory() as session:
            total = (
                await session.execute(text(COUNT_BASE), params)
            ).scalar_one()
            rows = await session.execute(
                text(f"{SELECT_BASE} {order_by} LIMIT :limit OFFSET :offset"),
                params,
            )
            insights = [self._insight_payload(row) for row in rows.mappings()]
            facets = await self._facets(session, tenant_id)
        return {
            "insights": insights,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_insight(
        self, *, tenant_id: uuid.UUID, insight_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One insight with its desglose: the hypotheses it restructures and
        the Active Context it operates on - all resolved from the canonical
        tables."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": insight_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            insight = self._insight_payload(row)
            hypothesis_ids = list(row["hypothesis_ids"] or [])
            context_id = row["context_id"]
            hypotheses = []
            context = None
            if hypothesis_ids:
                hyp_rows = await session.execute(
                    SELECT_HYPOTHESES,
                    {"tenant_id": tenant_id, "hypothesis_ids": hypothesis_ids},
                )
                hypotheses = [HypothesisReadStore._hypothesis_payload(h) for h in hyp_rows.mappings()]
                for h in hypotheses:
                    if "anomaly_ids" not in h or h["anomaly_ids"] is None:
                        h["anomaly_ids"] = []
            if context_id:
                ctx_row = await session.execute(
                    SELECT_CONTEXT,
                    {"tenant_id": tenant_id, "context_id": context_id},
                )
                ctx = ctx_row.mappings().one_or_none()
                if ctx:
                    context = ContextReadStore._context_payload(ctx)
        return {
            "insight": insight,
            "hypotheses": hypotheses,
            "context": context,
        }

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct hypothesis_ids and context_ids for the tenant (real
        values, not invented options) so the UI can offer honest filter
        choices."""
        cache_key = f"insights:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "hypothesis_ids": list(row["hypothesis_ids"] or []),
            "context_ids": list(row["context_ids"] or []),
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()
