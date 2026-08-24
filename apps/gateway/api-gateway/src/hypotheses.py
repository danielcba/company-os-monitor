"""Hypothesis READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the hypotheses table (P1) for a single tenant (the token's tenant
scope is enforced in GatewayService/health.py). A Hypothesis is a tentative,
testable explanation of an observed or anomalous situation (Reasoning ·
Predict): the generator proposes candidate explanations for each Anomaly,
paired with observable predicted consequences and a concrete falsification
criterion. This store pages, filters and sorts the candidate hypotheses and
resolves the desglose for one hypothesis: the anomalies it accounts for (from
the canonical anomalies table by ``anomaly_ids``), the expected patterns it
refers to (from ``pattern_ids``) and the Active Contexts of those anomalies
(from the canonical contexts table). It NEVER writes, never invents
explanations, never confirms or falsifies (that belongs to future evidence +
Confidence), and never reimplements the generator.

Content columns are immutable (P1, enforced by the content trigger on the
table); only ``status`` is a lifecycle field (candidate -> confirmed/falsified
is decided later by evidence + Confidence).
"""
import uuid
from typing import Any

from libs.shared.facets_cache import FacetsCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.contexts import ContextReadStore

SELECT_BASE = """
    SELECT id, tenant_id, anomaly_ids, pattern_ids, description,
           predicted_consequences, falsification_criterion, coherence_score,
           status, generated_at
    FROM hypotheses
    WHERE tenant_id = :tenant_id
      AND (CAST(:status AS VARCHAR) IS NULL OR status = :status)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM hypotheses
    WHERE tenant_id = :tenant_id
      AND (CAST(:status AS VARCHAR) IS NULL OR status = :status)
"""

SORT_CLAUSES = {
    "generated_at_desc": "ORDER BY generated_at DESC, id",
    "generated_at_asc": "ORDER BY generated_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT status ORDER BY status), '[]')
         FROM (SELECT status FROM hypotheses WHERE tenant_id = :tenant_id) t) AS statuses
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, anomaly_ids, pattern_ids, description,
           predicted_consequences, falsification_criterion, coherence_score,
           status, generated_at
    FROM hypotheses
    WHERE tenant_id = :tenant_id AND id = :id
    """
)

SELECT_ANOMALIES = text(
    """
    SELECT id, tenant_id, context_id, pattern_id,
           deviation_score, tolerance_threshold, anomaly_class, detected_at
    FROM anomalies
    WHERE tenant_id = :tenant_id AND id = ANY(:anomaly_ids)
    """
)

SELECT_PATTERNS = text(
    """
    SELECT id, tenant_id, context_id, pattern_type, description,
           strength_measure, frequency, detected_at, is_active
    FROM patterns
    WHERE tenant_id = :tenant_id AND id = ANY(:pattern_ids)
    """
)

SELECT_CONTEXTS = text(
    """
    SELECT id, tenant_id, evidence_ids, mental_model_id, purpose,
           coherence_score, competing_models, activated_at, is_active
    FROM contexts
    WHERE tenant_id = :tenant_id AND id = ANY(:context_ids)
    """
)


class HypothesisReadStore:
    """Persistence gateway for tenant-scoped, paginated hypothesis reads."""

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
    def _hypothesis_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable hypothesis row (a tentative,
        testable explanation with its predicted consequences and falsification
        criterion - P4)."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "anomaly_ids": [str(x) for x in row["anomaly_ids"]],
            "pattern_ids": [str(x) for x in (row["pattern_ids"] or [])],
            "description": row["description"],
            "predicted_consequences": list(row["predicted_consequences"] or []),
            "falsification_criterion": row["falsification_criterion"],
            "coherence_score": float(row["coherence_score"]),
            "status": row["status"],
            "generated_at": row["generated_at"].isoformat(),
        }

    @staticmethod
    def _anomaly_payload(row: Any) -> dict[str, Any]:
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

    @staticmethod
    def _pattern_payload(row: Any) -> dict[str, Any]:
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

    async def list_hypotheses(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        sort: str = "generated_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the tentative hypothesis stream."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["generated_at_desc"])
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
            hypotheses = [self._hypothesis_payload(row) for row in rows.mappings()]
            facets = await self._facets(session, tenant_id)
        return {
            "hypotheses": hypotheses,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_hypothesis(
        self, *, tenant_id: uuid.UUID, hypothesis_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One hypothesis with its desglose: the anomalies it accounts for, the
        expected patterns it refers to, and the Active Contexts of those
        anomalies - all resolved from the canonical tables."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": hypothesis_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            hypothesis = self._hypothesis_payload(row)
            anomaly_ids = list(row["anomaly_ids"])
            pattern_ids = list(row["pattern_ids"] or [])
            anomalies = []
            contexts: dict[str, dict[str, Any]] = {}
            context_ids: list[uuid.UUID] = []
            if anomaly_ids:
                anomaly_rows = await session.execute(
                    SELECT_ANOMALIES,
                    {"tenant_id": tenant_id, "anomaly_ids": anomaly_ids},
                )
                anomalies = [self._anomaly_payload(a) for a in anomaly_rows.mappings()]
                context_ids = sorted(
                    {uuid.UUID(a["context_id"]) for a in anomalies}
                )
                contexts = {str(cid): None for cid in context_ids}
            patterns = []
            if pattern_ids:
                pattern_rows = await session.execute(
                    SELECT_PATTERNS,
                    {"tenant_id": tenant_id, "pattern_ids": pattern_ids},
                )
                patterns = [self._pattern_payload(p) for p in pattern_rows.mappings()]
            if context_ids:
                ctx_rows = await session.execute(
                    SELECT_CONTEXTS,
                    {"tenant_id": tenant_id, "context_ids": context_ids},
                )
                for ctx in ctx_rows.mappings():
                    contexts[str(ctx["id"])] = ContextReadStore._context_payload(ctx)
        return {
            "hypothesis": hypothesis,
            "anomalies": anomalies,
            "patterns": patterns,
            "contexts": contexts,
        }

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct hypothesis statuses for the tenant (real values, not
        invented options) so the UI can offer honest filter choices."""
        cache_key = f"hypotheses:{tenant_id}"
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