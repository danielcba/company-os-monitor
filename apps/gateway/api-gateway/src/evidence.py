"""Evidence READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the immutable evidence table (P1) for a single tenant (the
token's tenant scope is enforced in GatewayService/health.py). Evidence
organizes existing observations (Perception - Organize); this store pages,
filters and sorts the append-only rows and resolves each evidence's
observation_ids back to the canonical observation rows (the desglose), so the
external product can render a truthful, paginated Evidence view with its
organized facts. It NEVER writes, never invents facts, never reimplements
perception logic (R3).
"""
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from libs.shared.facets_cache import FacetsCache

from src.observations import ObservationReadStore

SELECT_BASE = """
    SELECT id, tenant_id, observation_ids, organization_type, description,
           quality_class, weight, organized_at
    FROM evidence
    WHERE tenant_id = :tenant_id
      AND (CAST(:organization_type AS VARCHAR) IS NULL OR organization_type = :organization_type)
      AND (CAST(:quality_class AS VARCHAR) IS NULL OR quality_class = :quality_class)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM evidence
    WHERE tenant_id = :tenant_id
      AND (CAST(:organization_type AS VARCHAR) IS NULL OR organization_type = :organization_type)
      AND (CAST(:quality_class AS VARCHAR) IS NULL OR quality_class = :quality_class)
"""

SORT_CLAUSES = {
    "organized_at_desc": "ORDER BY organized_at DESC, id",
    "organized_at_asc": "ORDER BY organized_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT organization_type ORDER BY organization_type), '[]')
         FROM (SELECT organization_type FROM evidence WHERE tenant_id = :tenant_id) t) AS organization_types
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, observation_ids, organization_type, description,
           quality_class, weight, organized_at
    FROM evidence
    WHERE tenant_id = :tenant_id AND id = :id
    """
)

SELECT_OBSERVATIONS = text(
    """
    SELECT id, tenant_id, source_id, source_type, fact_type, fact_value,
           unit, captured_at, quality_class, raw_payload
    FROM observations
    WHERE tenant_id = :tenant_id AND id = ANY(:observation_ids)
    """
)

VALID_QUALITY_CLASSES = {"Q1", "Q2", "Q3", "Q4"}


class EvidenceReadStore:
    """Persistence gateway for tenant-scoped, paginated evidence reads."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache = FacetsCache()

    @staticmethod
    def _evidence_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable evidence row (organized
        facts; description is objective, never interpretation)."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "observation_ids": [str(x) for x in row["observation_ids"]],
            "organization_type": row["organization_type"],
            "description": row["description"],
            "quality_class": row["quality_class"],
            "weight": float(row["weight"]),
            "organized_at": row["organized_at"].isoformat(),
        }

    async def list_evidence(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        organization_type: str | None = None,
        quality_class: str | None = None,
        sort: str = "organized_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the append-only evidence rows."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["organized_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "organization_type": organization_type,
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
            evidence = [
                self._evidence_payload(row) for row in rows.mappings()
            ]
            facets = await self._facets(session, tenant_id)
        return {
            "evidence": evidence,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_evidence(
        self, *, tenant_id: uuid.UUID, evidence_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One evidence row with its observation desglose (the organized
        facts, resolved from the canonical immutable observations table)."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": evidence_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            evidence = self._evidence_payload(row)
            obs_rows = await session.execute(
                SELECT_OBSERVATIONS,
                {
                    "tenant_id": tenant_id,
                    "observation_ids": list(row["observation_ids"]),
                },
            )
            observations = [
                ObservationReadStore._observation_payload(o)
                for o in obs_rows.mappings()
            ]
        return {"evidence": evidence, "observations": observations}

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct organization types for the tenant (real values, not
        invented options) so the UI can offer honest filter choices."""
        cache_key = f"evidence:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "organization_types": list(row["organization_types"] or []),
            "quality_classes": sorted(VALID_QUALITY_CLASSES),
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()