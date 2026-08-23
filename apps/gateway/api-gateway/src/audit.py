"""Audit Log READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the immutable audit_log table (Episodic Memory) for a single
tenant (tenant scope is enforced in GatewayService/health.py). It pages,
filters and sorts the append-only audit rows so the external product can render
a truthful, paginated Audit view. It NEVER writes, never invents facts,
never reimplements cognitive logic (R3): the rows come straight from the
canonical audit_log table.
"""
import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from libs.shared.facets_cache import FacetsCache

SELECT_BASE = """
    SELECT id, tenant_id, user_id, policy_id, cognitive_layer,
           cognitive_concept, action, resource_type, resource_id,
           details, ip_address, user_agent, timestamp
    FROM audit_log
    WHERE tenant_id = :tenant_id
      AND (CAST(:user_id AS UUID) IS NULL OR user_id = :user_id)
      AND (CAST(:cognitive_layer AS VARCHAR) IS NULL OR cognitive_layer = :cognitive_layer)
      AND (CAST(:cognitive_concept AS VARCHAR) IS NULL OR cognitive_concept = :cognitive_concept)
      AND (CAST(:action AS VARCHAR) IS NULL OR action = :action)
      AND (CAST(:date_from AS TIMESTAMPTZ) IS NULL OR timestamp >= :date_from)
      AND (CAST(:date_to AS TIMESTAMPTZ) IS NULL OR timestamp <= :date_to)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM audit_log
    WHERE tenant_id = :tenant_id
      AND (CAST(:user_id AS UUID) IS NULL OR user_id = :user_id)
      AND (CAST(:cognitive_layer AS VARCHAR) IS NULL OR cognitive_layer = :cognitive_layer)
      AND (CAST(:cognitive_concept AS VARCHAR) IS NULL OR cognitive_concept = :cognitive_concept)
      AND (CAST(:action AS VARCHAR) IS NULL OR action = :action)
      AND (CAST(:date_from AS TIMESTAMPTZ) IS NULL OR timestamp >= :date_from)
      AND (CAST(:date_to AS TIMESTAMPTZ) IS NULL OR timestamp <= :date_to)
"""

SORT_CLAUSES = {
    "timestamp_desc": "ORDER BY timestamp DESC, id",
    "timestamp_asc": "ORDER BY timestamp ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT cognitive_layer ORDER BY cognitive_layer), '[]')
         FROM (SELECT cognitive_layer FROM audit_log WHERE tenant_id = :tenant_id) t) AS cognitive_layers,
      (SELECT COALESCE(jsonb_agg(DISTINCT cognitive_concept ORDER BY cognitive_concept), '[]')
         FROM (SELECT cognitive_concept FROM audit_log WHERE tenant_id = :tenant_id) t) AS cognitive_concepts,
      (SELECT COALESCE(jsonb_agg(DISTINCT action ORDER BY action), '[]')
         FROM (SELECT action FROM audit_log WHERE tenant_id = :tenant_id) t) AS actions
    """
)

VALID_SORTS = {"timestamp_desc", "timestamp_asc"}
VALID_COGNITIVE_LAYERS = {"perception", "reasoning", "confidence", "action", "memory"}
VALID_COGNITIVE_CONCEPTS = {
    "observation", "evidence", "context", "pattern", "anomaly",
    "hypothesis", "insight", "confidence", "recommendation", "decision",
}
VALID_ACTIONS = {
    "captured", "organized", "activated", "detected", "generated",
    "restructured", "calibrated", "proposed", "committed", "executed",
}


class AuditLogReadStore:
    """Persistence gateway for tenant-scoped, paginated audit log reads."""

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
        """jsonb can arrive decoded (asyncpg) or as a string; normalize."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    @staticmethod
    def _audit_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable audit log entry."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "user_id": str(row["user_id"]) if row["user_id"] else None,
            "policy_id": str(row["policy_id"]) if row["policy_id"] else None,
            "cognitive_layer": row["cognitive_layer"],
            "cognitive_concept": row["cognitive_concept"],
            "action": row["action"],
            "resource_type": row["resource_type"],
            "resource_id": str(row["resource_id"]),
            "details": AuditLogReadStore._as_json(row["details"]),
            "ip_address": str(row["ip_address"]) if row["ip_address"] else None,
            "user_agent": row["user_agent"],
            "timestamp": row["timestamp"].isoformat(),
        }

    async def list_audit_logs(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
        cognitive_layer: str | None = None,
        cognitive_concept: str | None = None,
        action: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "timestamp_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the append-only audit log rows."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["timestamp_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "user_id": uuid.UUID(user_id) if user_id else None,
            "cognitive_layer": cognitive_layer,
            "cognitive_concept": cognitive_concept,
            "action": action,
            "date_from": date_from,
            "date_to": date_to,
        }
        async with self._session_factory() as session:
            total = (
                await session.execute(text(COUNT_BASE), params)
            ).scalar_one()
            rows = await session.execute(
                text(f"{SELECT_BASE} {order_by} LIMIT :limit OFFSET :offset"),
                params,
            )
            entries = [
                self._audit_payload(row) for row in rows.mappings()
            ]
            facets = await self._facets(session, tenant_id)
        return {
            "entries": entries,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct cognitive layers, concepts and actions for the tenant."""
        cache_key = f"audit:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "cognitive_layers": list(row["cognitive_layers"] or []),
            "cognitive_concepts": list(row["cognitive_concepts"] or []),
            "actions": list(row["actions"] or []),
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()
