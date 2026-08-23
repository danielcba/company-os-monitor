"""Pattern READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the immutable patterns table (P1) for a single tenant (the
token's tenant scope is enforced in GatewayService/health.py). A Pattern is a
recurring structure detected within an Active Context (Reasoning ·
Generalize): the detector measures the support of the Pattern Library over the
context stream and appends Candidate Patterns with a strength_measure
(support/frequency/p-value). This store pages, filters and sorts the detected
patterns and resolves each pattern's context_id back to the canonical
contexts row (the desglose: the Active Context the regularity was detected
over). It NEVER writes, never invents regularities, never reimplements the
detector, and never explains causes — explanation belongs to Hypothesis (the
UI is the only consumer; P4 keeps Pattern as structure, not cause).
"""
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from libs.shared.facets_cache import FacetsCache

from src.contexts import ContextReadStore

SELECT_BASE = """
    SELECT id, tenant_id, context_id, pattern_type, description,
           strength_measure, frequency, detected_at, is_active
    FROM patterns
    WHERE tenant_id = :tenant_id
      AND (CAST(:pattern_type AS VARCHAR) IS NULL OR pattern_type = :pattern_type)
      AND (CAST(:is_active AS BOOLEAN) IS NULL OR is_active = :is_active)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM patterns
    WHERE tenant_id = :tenant_id
      AND (CAST(:pattern_type AS VARCHAR) IS NULL OR pattern_type = :pattern_type)
      AND (CAST(:is_active AS BOOLEAN) IS NULL OR is_active = :is_active)
"""

SORT_CLAUSES = {
    "detected_at_desc": "ORDER BY detected_at DESC, id",
    "detected_at_asc": "ORDER BY detected_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT pattern_type ORDER BY pattern_type), '[]')
         FROM (SELECT pattern_type FROM patterns WHERE tenant_id = :tenant_id) t) AS pattern_types
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, context_id, pattern_type, description,
           strength_measure, frequency, detected_at, is_active
    FROM patterns
    WHERE tenant_id = :tenant_id AND id = :id
    """
)

SELECT_CONTEXT = text(
    """
    SELECT id, tenant_id, evidence_ids, mental_model_id, purpose,
           coherence_score, competing_models, activated_at, is_active
    FROM contexts
    WHERE tenant_id = :tenant_id AND id = :id
    """
)


class PatternReadStore:
    """Persistence gateway for tenant-scoped, paginated pattern reads."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache = FacetsCache()

    @staticmethod
    def _pattern_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable pattern row (the detected
        regularity with its measured support - P4)."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "context_id": str(row["context_id"]),
            "pattern_type": row["pattern_type"],
            "description": row["description"],
            "strength_measure": float(row["strength_measure"]),
            "frequency": row["frequency"],
            "detected_at": row["detected_at"].isoformat(),
            "is_active": bool(row["is_active"]),
        }

    async def list_patterns(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        pattern_type: str | None = None,
        is_active: bool | None = None,
        sort: str = "detected_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the append-only pattern stream."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["detected_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "pattern_type": pattern_type,
            "is_active": is_active,
        }
        async with self._session_factory() as session:
            total = (
                await session.execute(text(COUNT_BASE), params)
            ).scalar_one()
            rows = await session.execute(
                text(f"{SELECT_BASE} {order_by} LIMIT :limit OFFSET :offset"),
                params,
            )
            patterns = [self._pattern_payload(row) for row in rows.mappings()]
            facets = await self._facets(session, tenant_id)
        return {
            "patterns": patterns,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_pattern(
        self, *, tenant_id: uuid.UUID, pattern_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One pattern row with its context desglose (the Active Context the
        regularity was detected over, resolved from the canonical immutable
        contexts table)."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": pattern_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            pattern = self._pattern_payload(row)
            ctx_row = (
                await session.execute(
                    SELECT_CONTEXT,
                    {"tenant_id": tenant_id, "id": row["context_id"]},
                )
            ).mappings().one_or_none()
            context = (
                ContextReadStore._context_payload(ctx_row)
                if ctx_row is not None
                else None
            )
        return {"pattern": pattern, "context": context}

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct pattern types for the tenant (real values, not invented
        options) so the UI can offer honest filter choices."""
        cache_key = f"patterns:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "pattern_types": list(row["pattern_types"] or []),
            "is_active": ["true", "false"],
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()