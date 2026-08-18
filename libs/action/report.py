"""Report model + append-only persistence (external NON-canonical output, ADR-0002).

A Report is NOT a cognitive capability. ADR-0002 governs this module: the
canonical flow (Perception -> Reasoning -> Confidence -> Action) is the brain;
everything else is non-canonical and must originate its judgments from the
central cognitive flow. The Report Generator only FORMATS what the flow already
committed (Decision(s), Recommendation(s), Active Context(s), Confidence scores
and the supporting trace) - it never generates judgments, never creates
recommendations or decisions, and never writes to the cognitive tables (P1).
Its ONLY output table is ``reports`` (the report-service's own, non-canonical).

Family placement: ``libs/action/`` groups the Action-layer artifacts
(Recommendation/Propose, Decision/Commit). The Report formats exactly those
artifacts, so it lives here as the output-document family of the Action layer.
The module is explicitly non-canonical: its rows are append-only output
documents, never cognitive input.

P1 vs reports: ``reports`` is the report-service's OWN output table
(non-canonical), NOT a cognitive chain table. P1's precedent (append-only +
immutable content) applies to the canonical chain; for reports we adopt
append-only with a content immutability trigger as a COMPLIANCE choice: a
report that was generated and served (potentially cited in an audit) must not
be retroactively modified. The deterministic ``report_id`` (tenant + report_type
+ period, uuid5) makes re-generating the SAME report of the SAME period
idempotent (dedup by primary key); ``generated_at`` is deliberately NOT part of
the id (idempotence between runs). ``ai_generated`` stays FALSE and
``model_used`` stays NULL in this MVP: reports are rendered by local templates,
LM Studio arrives in a future sprint (Sprint 18).
"""
import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Fixed namespace for deterministic report ids (content-addressed, idempotent).
REPORT_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000083")

# Report types of the product (docs/04 FASE 6). The report-service renders
# executive/technical/json in this sprint; compliance is a future phase.
REPORT_TYPE_EXECUTIVE = "executive"
REPORT_TYPE_TECHNICAL = "technical"
REPORT_TYPE_COMPLIANCE = "compliance"
REPORT_TYPE_JSON = "json"
REPORT_TYPES: frozenset[str] = frozenset(
    {
        REPORT_TYPE_EXECUTIVE,
        REPORT_TYPE_TECHNICAL,
        REPORT_TYPE_COMPLIANCE,
        REPORT_TYPE_JSON,
    }
)


def report_id(
    tenant_id: uuid.UUID,
    report_type: str,
    period_start: date,
    period_end: date,
) -> uuid.UUID:
    """Derive a deterministic id from the report identity.

    Anchors on the tenant, the report type and the covered period. Re-generating
    the SAME report of the SAME period yields the same id (dedup by primary key,
    ON CONFLICT DO NOTHING). ``generated_at`` and the rendered content are
    deliberately EXCLUDED: they would break idempotence between runs. A report
    of a DIFFERENT period (e.g. the next daily window) gets a distinct id and is
    appended, never an UPDATE (append-only output trail).
    """
    return uuid.uuid5(
        REPORT_NAMESPACE,
        f"{tenant_id}:{report_type}:{period_start.isoformat()}:{period_end.isoformat()}",
    )


class ReportCreate(BaseModel):
    """Creation request for a generated Report (content only, no lifecycle).

    Fields mirror the ``reports`` table (docs/01). ``content`` is the rendered
    document (the dict produced by the pure renderers); ``file_path`` is the
    artifact written to ``REPORT_OUTPUT_DIR`` (PDF for executive/technical,
    JSON for the json report). ``ai_generated`` defaults to FALSE and
    ``model_used`` to NULL: in this MVP reports are rendered by local templates;
    LM Studio arrives in a future sprint (Sprint 18).
    """

    tenant_id: uuid.UUID
    report_type: str
    title: str
    summary: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    ai_generated: bool = False
    model_used: str | None = None
    period_start: date
    period_end: date
    file_path: str | None = None

    model_config = ConfigDict(frozen=True)


class Report(BaseModel):
    """Immutable generated Report row (external non-canonical output, ADR-0002).

    The row is append-only and fully immutable (content trigger): every column
    is assigned at generation. It always records what was rendered
    (``content``), for whom (``tenant_id``), the ``report_type``, the covered
    ``period_start``/``period_end`` and the written artifact (``file_path``),
    so a served report stays auditable and is never retroactively modified.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    report_type: str
    title: str
    summary: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    ai_generated: bool = False
    model_used: str | None = None
    period_start: date
    period_end: date
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    file_path: str | None = None

    model_config = ConfigDict(frozen=True)


def build_report(create: ReportCreate) -> Report:
    """Materialize a Report from a creation request (id assigned at creation)."""
    return Report(
        id=report_id(
            create.tenant_id,
            create.report_type,
            create.period_start,
            create.period_end,
        ),
        tenant_id=create.tenant_id,
        report_type=create.report_type,
        title=create.title,
        summary=create.summary,
        content=create.content,
        ai_generated=create.ai_generated,
        model_used=create.model_used,
        period_start=create.period_start,
        period_end=create.period_end,
        file_path=create.file_path,
    )


INSERT_REPORT = text(
    """
    INSERT INTO reports (
        id, tenant_id, report_type, title, summary, content, ai_generated,
        model_used, period_start, period_end, generated_at, file_path
    )
    VALUES (
        :id, :tenant_id, :report_type, :title,
        CAST(:summary AS varchar), CAST(:content AS jsonb),
        CAST(:ai_generated AS boolean), CAST(:model_used AS varchar),
        :period_start, :period_end, :generated_at, CAST(:file_path AS varchar)
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, report_type, title, summary, content,
              ai_generated, model_used, period_start, period_end,
              generated_at, file_path
    """
)

CHECK_REPORT_EXISTS = text("SELECT 1 FROM reports WHERE id = :id")

SELECT_REPORTS = text(
    """
    SELECT id, tenant_id, report_type, title, summary, content, ai_generated,
           model_used, period_start, period_end, generated_at, file_path
    FROM reports
    WHERE tenant_id = :tenant_id
      AND (CAST(:report_type AS varchar) IS NULL
           OR report_type = CAST(:report_type AS varchar))
    ORDER BY generated_at DESC, id
    """
)

SELECT_REPORT_BY_ID = text(
    """
    SELECT id, tenant_id, report_type, title, summary, content, ai_generated,
           model_used, period_start, period_end, generated_at, file_path
    FROM reports
    WHERE id = :id
    """
)

SELECT_TENANT_REPORT_IDS = text("SELECT DISTINCT tenant_id FROM reports")

SELECT_TENANT = text(
    "SELECT id, name, slug FROM tenants WHERE id = :tenant_id"
)


class ReportStore:
    """Persistence gateway for the Report Store (PostgreSQL reports, output table).

    READ-only over the cognitive flow (it never touches the canonical tables -
    P1) and INSERT-only over its own ``reports`` output table, with idempotent
    dedup by the deterministic content-addressed id.
    """

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_report(self, report: Report) -> dict[str, Any] | None:
        """Insert one immutable report row (append-only output).

        Returns the persisted row, or None when it was already present
        (idempotent dedup by the deterministic content-addressed id).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_REPORT,
                {
                    "id": report.id,
                    "tenant_id": report.tenant_id,
                    "report_type": report.report_type,
                    "title": report.title,
                    "summary": report.summary,
                    "content": json.dumps(report.content, default=str),
                    "ai_generated": report.ai_generated,
                    "model_used": report.model_used,
                    "period_start": report.period_start,
                    "period_end": report.period_end,
                    "generated_at": report.generated_at,
                    "file_path": report.file_path,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return self._row_to_dict(row) if row is not None else None

    async def report_exists(self, *, id: uuid.UUID) -> bool:
        """Check existence (used to avoid duplicating reports on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_REPORT_EXISTS, {"id": id})
            return result.scalar() is not None

    async def list_reports(
        self, *, tenant_id: uuid.UUID, report_type: str | None = None
    ) -> list[Report]:
        """Read-only load of the generated report rows for a tenant."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_REPORTS,
                {"tenant_id": tenant_id, "report_type": report_type},
            )
            reports = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["content"], str):
                    row["content"] = json.loads(row["content"])
                reports.append(Report(**row))
            return reports

    async def get_report(self, *, id: uuid.UUID) -> Report | None:
        """Read-only load of one report row by id."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_REPORT_BY_ID, {"id": id})
            row = result.mappings().one_or_none()
            if row is None:
                return None
            data = dict(row)
            if isinstance(data["content"], str):
                data["content"] = json.loads(data["content"])
            return Report(**data)

    async def list_tenant_ids(self) -> list[uuid.UUID]:
        """Tenants that currently have at least one Report row."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_REPORT_IDS)
            return [row[0] for row in result.all()]

    async def get_tenant(self, *, tenant_id: uuid.UUID) -> dict[str, Any] | None:
        """Read-only load of the support ``tenants`` row (report header).

        The report header needs the tenant name/slug (docs/04 Executive
        Summary: "Tenant: ACME Corp"). Reading the support table is READ-only;
        the report-service never writes outside ``reports`` (P1).
        """
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT, {"tenant_id": tenant_id})
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        data = dict(row)
        if isinstance(data.get("content"), str):
            data["content"] = json.loads(data["content"])
        return data