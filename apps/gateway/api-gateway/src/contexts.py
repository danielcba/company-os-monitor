"""Context READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the immutable contexts table (P1) for a single tenant (the
token's tenant scope is enforced in GatewayService/health.py). Context is the
Active interpretation selected by explanatory coherence competition (P2); this
store pages, filters and sorts the activation stream and resolves each
context's evidence_ids back to the canonical evidence rows (the desglose), so
the external product can render a truthful, paginated Contexts view with its
winner mental model, coherence score and competing models. It NEVER writes,
never invents interpretations, never reimplements the activator (R3).
"""
import json
import uuid
from typing import Any

from libs.shared.facets_cache import FacetsCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.evidence import EvidenceReadStore

SELECT_BASE = """
    SELECT id, tenant_id, evidence_ids, mental_model_id, purpose,
           coherence_score, competing_models, activated_at, is_active
    FROM contexts
    WHERE tenant_id = :tenant_id
      AND (CAST(:purpose AS VARCHAR) IS NULL OR purpose = :purpose)
      AND (CAST(:mental_model_id AS VARCHAR) IS NULL OR mental_model_id = :mental_model_id)
      AND (CAST(:is_active AS BOOLEAN) IS NULL OR is_active = :is_active)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM contexts
    WHERE tenant_id = :tenant_id
      AND (CAST(:purpose AS VARCHAR) IS NULL OR purpose = :purpose)
      AND (CAST(:mental_model_id AS VARCHAR) IS NULL OR mental_model_id = :mental_model_id)
      AND (CAST(:is_active AS BOOLEAN) IS NULL OR is_active = :is_active)
"""

SORT_CLAUSES = {
    "activated_at_desc": "ORDER BY activated_at DESC, id",
    "activated_at_asc": "ORDER BY activated_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT purpose ORDER BY purpose), '[]')
         FROM (SELECT purpose FROM contexts WHERE tenant_id = :tenant_id) t) AS purposes,
      (SELECT COALESCE(jsonb_agg(DISTINCT mental_model_id ORDER BY mental_model_id), '[]')
         FROM (SELECT mental_model_id FROM contexts WHERE tenant_id = :tenant_id) t) AS mental_model_ids
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, evidence_ids, mental_model_id, purpose,
           coherence_score, competing_models, activated_at, is_active
    FROM contexts
    WHERE tenant_id = :tenant_id AND id = :id
    """
)

SELECT_EVIDENCE = text(
    """
    SELECT id, tenant_id, observation_ids, organization_type, description,
           quality_class, weight, organized_at
    FROM evidence
    WHERE tenant_id = :tenant_id AND id = ANY(:evidence_ids)
    """
)


class ContextReadStore:
    """Persistence gateway for tenant-scoped, paginated context reads."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
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
    def _context_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable context row (winner model,
        coherence score and competing models as activated - P2)."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "evidence_ids": [str(x) for x in row["evidence_ids"]],
            "mental_model_id": row["mental_model_id"],
            "purpose": row["purpose"],
            "coherence_score": float(row["coherence_score"]),
            "competing_models": ContextReadStore._as_json(row["competing_models"]),
            "activated_at": row["activated_at"].isoformat(),
            "is_active": bool(row["is_active"]),
        }

    async def list_contexts(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        purpose: str | None = None,
        mental_model_id: str | None = None,
        is_active: bool | None = None,
        sort: str = "activated_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the append-only context stream."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["activated_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "purpose": purpose,
            "mental_model_id": mental_model_id,
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
            contexts = [self._context_payload(row) for row in rows.mappings()]
            facets = await self._facets(session, tenant_id)
        return {
            "contexts": contexts,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_context(
        self, *, tenant_id: uuid.UUID, context_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One context row with its evidence desglose (the organized facts
        that supported the winning model, resolved from the canonical
        immutable evidence table)."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": context_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            context = self._context_payload(row)
            ev_rows = await session.execute(
                SELECT_EVIDENCE,
                {
                    "tenant_id": tenant_id,
                    "evidence_ids": list(row["evidence_ids"]),
                },
            )
            evidence = [
                EvidenceReadStore._evidence_payload(e)
                for e in ev_rows.mappings()
            ]
        return {"context": context, "evidence": evidence}

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct purposes and mental models for the tenant (real values,
        not invented options) so the UI can offer honest filter choices."""
        cache_key = f"contexts:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "purposes": list(row["purposes"] or []),
            "mental_model_ids": list(row["mental_model_ids"] or []),
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