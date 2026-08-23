"""Report READ store for the API Gateway (external capability, ADR-0002).

Pure READ of the reports table (the report-service's OWN output table,
non-canonical) for a single tenant (the token's tenant scope is enforced in
GatewayService/health.py). A Report is a FORMATTED output document of the Report
Generator (ADR-0002): it only FORMATS what the canonical flow already committed
(Decision(s), Recommendation(s), Confidence scores and the supporting trace) —
it never generates judgments. Each row records the rendered ``content`` (the
dict produced by the pure renderers), the ``report_type``, the covered
``period_start``/``period_end`` and the written artifact (``file_path``);
``ai_generated`` stays FALSE and ``model_used`` NULL in this MVP (reports are
rendered by local templates; LM Studio arrives in a future sprint). Rows are
append-only and fully immutable (content trigger): a served report stays
auditable and is never retroactively modified.

This store pages, filters and sorts the generated reports and resolves the
detail for one row: the full report (with its rendered content) plus the
support ``tenants`` header (name/slug) used by the report title. It NEVER
writes, never generates reports and never reimplements the renderers.
"""
import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from libs.shared.facets_cache import FacetsCache

REPORT_TYPES = ("executive", "technical", "compliance", "json")

SELECT_BASE = """
    SELECT id, tenant_id, report_type, title, summary, content, ai_generated,
           model_used, period_start, period_end, generated_at, file_path
    FROM reports
    WHERE tenant_id = :tenant_id
      AND (CAST(:report_type AS VARCHAR) IS NULL OR report_type = :report_type)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM reports
    WHERE tenant_id = :tenant_id
      AND (CAST(:report_type AS VARCHAR) IS NULL OR report_type = :report_type)
"""

SORT_CLAUSES = {
    "generated_at_desc": "ORDER BY generated_at DESC, id",
    "generated_at_asc": "ORDER BY generated_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT report_type ORDER BY report_type), '[]')
         FROM (SELECT report_type FROM reports WHERE tenant_id = :tenant_id) t) AS report_types
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, report_type, title, summary, content, ai_generated,
           model_used, period_start, period_end, generated_at, file_path
    FROM reports
    WHERE tenant_id = :tenant_id AND id = :id
    """
)

SELECT_TENANT = text(
    "SELECT id, name, slug FROM tenants WHERE id = :tenant_id"
)


class ReportReadStore:
    """Persistence gateway for tenant-scoped, paginated report reads."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache = FacetsCache()

    @staticmethod
    def _report_payload(row: Any, *, include_content: bool = False) -> dict[str, Any]:
        """JSON-native READ view of an immutable report row (the formatted
        output document - ADR-0002: formats what the flow committed, never
        generates judgments). ``content`` (the rendered document) is included
        only on the detail view to keep the list light."""
        payload = {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "report_type": row["report_type"],
            "title": row["title"],
            "summary": row["summary"],
            "ai_generated": bool(row["ai_generated"]),
            "model_used": row["model_used"],
            "period_start": (
                row["period_start"].isoformat()
                if row["period_start"] is not None
                else None
            ),
            "period_end": (
                row["period_end"].isoformat() if row["period_end"] is not None else None
            ),
            "generated_at": row["generated_at"].isoformat(),
            "file_path": row["file_path"],
        }
        if include_content:
            content = row["content"]
            if isinstance(content, str):
                content = json.loads(content)
            payload["content"] = content
        return payload

    async def list_reports(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        report_type: str | None = None,
        sort: str = "generated_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the generated report stream."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["generated_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "report_type": report_type,
        }
        async with self._session_factory() as session:
            total = (
                await session.execute(text(COUNT_BASE), params)
            ).scalar_one()
            rows = await session.execute(
                text(f"{SELECT_BASE} {order_by} LIMIT :limit OFFSET :offset"),
                params,
            )
            reports = [
                self._report_payload(row) for row in rows.mappings()
            ]
            facets = await self._facets(session, tenant_id)
        return {
            "reports": reports,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_report(
        self, *, tenant_id: uuid.UUID, report_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One report with its rendered content and the tenant header."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": report_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            report = self._report_payload(row, include_content=True)
            tenant_row = (
                await session.execute(SELECT_TENANT, {"tenant_id": tenant_id})
            ).mappings().one_or_none()
            tenant = dict(tenant_row) if tenant_row is not None else None
        return {
            "report": report,
            "tenant": {
                "id": str(tenant["id"]),
                "name": tenant["name"],
                "slug": tenant["slug"],
            }
            if tenant is not None
            else None,
        }

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct report types for the tenant (real values, not invented
        options) so the UI can offer honest filter choices."""
        cache_key = f"reports:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "report_types": list(row["report_types"] or []),
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()