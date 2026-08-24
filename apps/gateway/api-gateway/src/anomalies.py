"""Anomaly READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the immutable anomalies table (P1) for a single tenant (the
token's tenant scope is enforced in GatewayService/health.py). An Anomaly is a
detected deviation from a Pattern over an Active Context (Reasoning · Detect
Deviation): the deviation_score exceeds the tolerance_threshold. This store
pages, filters and sorts the detected anomalies and resolves each anomaly's
context_id back to the canonical contexts row (the desglose: the Active Context
the regularity was detected over). It NEVER writes, never invents deviations,
never reimplements the detector, and never explains causes — explanation belongs
to Hypothesis (the UI is the only consumer; P4 keeps Anomaly as structure, not
cause).

The deterministic ``anomaly_id`` includes the tenant, the Active Context and
the expected Pattern it deviates from, so re-detecting over the same facts
produces the same id (idempotent dedup by primary key).
"""
import uuid
from typing import Any

from libs.shared.facets_cache import FacetsCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.contexts import ContextReadStore

SELECT_BASE = """
    SELECT id, tenant_id, context_id, pattern_id,
           deviation_score, tolerance_threshold, anomaly_class, detected_at
    FROM anomalies
    WHERE tenant_id = :tenant_id
      AND (CAST(:anomaly_class AS VARCHAR) IS NULL OR anomaly_class = :anomaly_class)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM anomalies
    WHERE tenant_id = :tenant_id
      AND (CAST(:anomaly_class AS VARCHAR) IS NULL OR anomaly_class = :anomaly_class)
"""

SORT_CLAUSES = {
    "detected_at_desc": "ORDER BY detected_at DESC, id",
    "detected_at_asc": "ORDER BY detected_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT anomaly_class ORDER BY anomaly_class), '[]')
         FROM (SELECT anomaly_class FROM anomalies WHERE tenant_id = :tenant_id) t) AS anomaly_classes
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, context_id, pattern_id,
           deviation_score, tolerance_threshold, anomaly_class, detected_at
    FROM anomalies
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


class AnomalyReadStore:
    """Persistence gateway for tenant-scoped, paginated anomaly reads."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache = FacetsCache()

    @staticmethod
    def _anomaly_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable anomaly row (the detected
        deviation with its quantified score - P4)."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "context_id": str(row["context_id"]),
            "pattern_id": str(row["pattern_id"]) if row["pattern_id"] else None,
            "anomaly_class": row["anomaly_class"],
            "deviation_score": float(row["deviation_score"]),
            "tolerance_threshold": float(row["tolerance_threshold"]),
            "detected_at": row["detected_at"].isoformat(),
        }

    async def list_anomalies(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        anomaly_class: str | None = None,
        sort: str = "detected_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the append-only anomaly stream."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["detected_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "anomaly_class": anomaly_class,
        }
        async with self._session_factory() as session:
            total = (
                await session.execute(text(COUNT_BASE), params)
            ).scalar_one()
            rows = await session.execute(
                text(f"{SELECT_BASE} {order_by} LIMIT :limit OFFSET :offset"),
                params,
            )
            anomalies = [self._anomaly_payload(row) for row in rows.mappings()]
            facets = await self._facets(session, tenant_id)
        return {
            "anomalies": anomalies,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_anomaly(
        self, *, tenant_id: uuid.UUID, anomaly_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One anomaly row with its context desglose (the Active Context the
        deviation was detected over, resolved from the canonical immutable
        contexts table)."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": anomaly_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            anomaly = self._anomaly_payload(row)
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
        return {"anomaly": anomaly, "context": context}

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct anomaly classes for the tenant (real values, not invented
        options) so the UI can offer honest filter choices."""
        cache_key = f"anomalies:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "anomaly_classes": list(row["anomaly_classes"] or []),
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()