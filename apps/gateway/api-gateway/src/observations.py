"""Observation READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the immutable observations table (P1) for a single tenant (the
token's tenant scope is enforced in GatewayService/health.py). It pages,
filters and sorts the append-only rows so the external product can render a
truthful, paginated Observations view. It NEVER writes, never invents facts,
never reimplements perception logic (R3): the rows come straight from the
canonical observation store.
"""
import json
import uuid
from typing import Any

from libs.shared.facets_cache import FacetsCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

SELECT_BASE = """
    SELECT id, tenant_id, source_id, source_type, fact_type, fact_value,
           unit, captured_at, quality_class, raw_payload
    FROM observations
    WHERE tenant_id = :tenant_id
      AND (CAST(:fact_type AS VARCHAR) IS NULL OR fact_type = :fact_type)
      AND (CAST(:source_type AS VARCHAR) IS NULL OR source_type = :source_type)
      AND (CAST(:quality_class AS VARCHAR) IS NULL OR quality_class = :quality_class)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM observations
    WHERE tenant_id = :tenant_id
      AND (CAST(:fact_type AS VARCHAR) IS NULL OR fact_type = :fact_type)
      AND (CAST(:source_type AS VARCHAR) IS NULL OR source_type = :source_type)
      AND (CAST(:quality_class AS VARCHAR) IS NULL OR quality_class = :quality_class)
"""

SORT_CLAUSES = {
    "captured_at_desc": "ORDER BY captured_at DESC, id",
    "captured_at_asc": "ORDER BY captured_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT fact_type ORDER BY fact_type), '[]')
         FROM (SELECT fact_type FROM observations WHERE tenant_id = :tenant_id) t) AS fact_types,
      (SELECT COALESCE(jsonb_agg(DISTINCT source_type ORDER BY source_type), '[]')
         FROM (SELECT source_type FROM observations WHERE tenant_id = :tenant_id) t) AS source_types,
      (SELECT COALESCE(jsonb_agg(DISTINCT quality_class ORDER BY quality_class), '[]')
         FROM (SELECT quality_class FROM observations WHERE tenant_id = :tenant_id) t) AS quality_classes
    """
)

VALID_QUALITY_CLASSES = {"Q1", "Q2", "Q3", "Q4"}


class ObservationReadStore:
    """Persistence gateway for tenant-scoped, paginated observation reads."""

    def __init__(self, dsn: str | None = None, engine: AsyncEngine | None = None, pool_size: int = 10, max_overflow: int = 20):
        if engine is not None:
            self._engine = engine
        else:
            self._engine = create_async_engine(
                dsn,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache = FacetsCache()

    @staticmethod
    def _as_json(value: Any) -> Any:
        """jsonb can arrive decoded (asyncpg) or as a string; normalize to
        the JSON-native value the UI renders."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    @staticmethod
    def _observation_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable observation (fact, no
        interpretation: fact_type/fact_value/unit are shown as captured)."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "source_id": str(row["source_id"]),
            "source_type": row["source_type"],
            "fact_type": row["fact_type"],
            "fact_value": ObservationReadStore._as_json(row["fact_value"]),
            "unit": row["unit"],
            "captured_at": row["captured_at"].isoformat(),
            "quality_class": row["quality_class"],
            "raw_payload": ObservationReadStore._as_json(row["raw_payload"]),
        }

    async def list_observations(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        fact_type: str | None = None,
        source_type: str | None = None,
        quality_class: str | None = None,
        sort: str = "captured_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the append-only observation rows."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["captured_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "fact_type": fact_type,
            "source_type": source_type,
            "quality_class": quality_class,
        }
        async with self._session_factory() as session:
            total = (
                await session.execute(text(COUNT_BASE), params)
            ).scalar_one()
            rows = await session.execute(
                text(f"{SELECT_BASE} {order_by} LIMIT :limit OFFSET :offset"),
                params,
            )
            observations = [
                self._observation_payload(row) for row in rows.mappings()
            ]
            facets = await self._facets(session, tenant_id)
        return {
            "observations": observations,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct fact/source types for the tenant (real values, not
        invented options) so the UI can offer honest filter choices."""
        cache_key = f"observations:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "fact_types": list(row["fact_types"] or []),
            "source_types": list(row["source_types"] or []),
            "quality_classes": list(row["quality_classes"] or []),
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()
