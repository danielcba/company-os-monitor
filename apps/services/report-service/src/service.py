"""Report Service - external NON-canonical output orchestration (ADR-0002).

The Report Generator is NOT a cognitive capability (R1 does not apply): it is
a non-canonical external capability (ADR-0002) whose only contract is
READ the canonical flow -> FORMAT -> OUTPUT. Per tenant it reads the pipeline
tables (decisions, recommendations, contexts, confidence_scores, hypotheses,
anomalies, patterns, evidence, observations - ALL read-only, P1) and renders a
Report document (executive/technical/json) that formats what the flow ALREADY
committed. It NEVER writes to the cognitive tables (P1) - its only output table
is ``reports`` (its own, non-canonical) - and never reads the observation bus.

The renderers are PURE (no I/O): the orchestrator reads the data, builds a
``ReportSource`` bundle, calls the renderer for the requested report_type,
writes the output artifact (PDF via weasyprint for executive/technical, JSON
for the json report) into REPORT_OUTPUT_DIR and persists the row in ``reports``
with idempotent dedup by the deterministic report id (same tenant + type +
period -> same id -> ON CONFLICT DO NOTHING).
"""
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from libs.action.decision import DecisionStore
from libs.action.recommendation import RecommendationStore
from libs.action.report import (
    REPORT_TYPE_EXECUTIVE,
    REPORT_TYPE_JSON,
    REPORT_TYPE_TECHNICAL,
    ReportCreate,
    ReportStore,
    build_report,
    report_id,
)
from libs.learning.confidence import ConfidenceStore
from libs.perception.context import ContextStore
from libs.perception.evidence import EvidenceStore
from libs.perception.store import ObservationStore
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore
from libs.reasoning.pattern import PatternStore

from src.renderers import (
    ReportSource,
    render_executive,
    render_json,
    render_technical,
    to_html,
    to_json,
    to_pdf,
)

RENDERABLE_TYPES: tuple[str, ...] = (
    REPORT_TYPE_EXECUTIVE,
    REPORT_TYPE_TECHNICAL,
    REPORT_TYPE_JSON,
)


class ReportService:
    """Orchestrates the Report generation cycle (READ flow -> FORMAT -> OUTPUT)."""

    def __init__(
        self,
        decision_store: DecisionStore,
        recommendation_store: RecommendationStore,
        context_store: ContextStore,
        confidence_store: ConfidenceStore,
        hypothesis_store: HypothesisStore,
        anomaly_store: AnomalyStore,
        pattern_store: PatternStore,
        evidence_store: EvidenceStore,
        observation_store: ObservationStore,
        report_store: ReportStore,
        output_dir: str = "reports-output",
        report_types: tuple[str, ...] = RENDERABLE_TYPES,
    ):
        self.decision_store = decision_store
        self.recommendation_store = recommendation_store
        self.context_store = context_store
        self.confidence_store = confidence_store
        self.hypothesis_store = hypothesis_store
        self.anomaly_store = anomaly_store
        self.pattern_store = pattern_store
        self.evidence_store = evidence_store
        self.observation_store = observation_store
        self.report_store = report_store
        self.output_dir = output_dir
        self.report_types = report_types
        self.total_reports = 0
        self.total_report_duplicates = 0
        self.total_errors = 0
        self.by_type: Counter[str] = Counter()
        self.render_duration_seconds = 0.0
        self.last_run_at: datetime | None = None

    async def run_report_cycle(self) -> int:
        """Generate every renderable report type for every tenant with Decisions."""
        tenants = await self.decision_store.list_tenant_ids()
        for tenant_id in tenants:
            for report_type in self.report_types:
                try:
                    await self.generate(tenant_id, report_type)
                except Exception:  # noqa: BLE001 - deliberate robustness per repo pattern
                    self.total_errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.total_reports

    async def generate(
        self, tenant_id, report_type: str
    ) -> tuple[Any, str]:
        """Generate ONE report document for a tenant (idempotent, never bypass).

        Returns ``(report, status)`` where status is ``created`` (a new row was
        appended) or ``duplicate`` (the same report of the same period already
        exists - dedup by deterministic id, no row added).
        """
        if report_type not in self.report_types:
            raise ValueError(f"unsupported report type: {report_type}")

        decisions = await self.decision_store.list_decisions(tenant_id=tenant_id)
        period_start, period_end = self._report_period(decisions)

        tenant = await self.report_store.get_tenant(tenant_id=tenant_id)
        if tenant is None:
            tenant = {
                "id": tenant_id,
                "name": str(tenant_id),
                "slug": "",
            }

        source = ReportSource(
            tenant=tenant,
            decisions=tuple(decisions),
            recommendations=tuple(
                await self.recommendation_store.list_recommendations(
                    tenant_id=tenant_id
                )
            ),
            contexts=tuple(await self.context_store.list_contexts(tenant_id=tenant_id)),
            confidences=tuple(
                await self.confidence_store.list_confidence(tenant_id=tenant_id)
            ),
            hypotheses=tuple(
                await self.hypothesis_store.list_hypotheses(tenant_id=tenant_id)
            ),
            anomalies=tuple(
                await self.anomaly_store.list_anomalies(tenant_id=tenant_id)
            ),
            patterns=tuple(await self.pattern_store.list_patterns(tenant_id=tenant_id)),
            evidence=tuple(await self.evidence_store.list_evidence(tenant_id=tenant_id)),
            observations=tuple(
                await self.observation_store.list_observations(tenant_id=tenant_id)
            ),
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(UTC),
        )

        started = time.perf_counter()
        content, extension, payload = await self._render(report_type, source)
        file_path = self._write_artifact(
            tenant_id, report_type, period_start, period_end, extension, payload
        )
        self.render_duration_seconds += time.perf_counter() - started

        create = ReportCreate(
            tenant_id=tenant_id,
            report_type=report_type,
            title=content["title"],
            summary=self._summarize(content, report_type),
            content=content,
            ai_generated=False,
            model_used=None,
            period_start=period_start,
            period_end=period_end,
            file_path=file_path,
        )
        report = build_report(create)
        row = await self.report_store.save_report(report)
        if row is not None:
            self.total_reports += 1
            self.by_type[report_type] += 1
            return report, "created"
        self.total_report_duplicates += 1
        return report, "duplicate"

    async def list_reports(
        self, tenant_id, report_type: str | None = None
    ) -> list[Any]:
        """Read-only listing of the generated report rows for a tenant."""
        return await self.report_store.list_reports(
            tenant_id=tenant_id, report_type=report_type
        )

    async def _render(
        self, report_type: str, source: ReportSource
    ) -> tuple[dict[str, Any], str, bytes]:
        """Render the document (pure renderer) and serialize to the artifact."""
        if report_type == REPORT_TYPE_EXECUTIVE:
            content = render_executive(source)
            return content, "pdf", to_pdf(to_html(content))
        if report_type == REPORT_TYPE_TECHNICAL:
            content = render_technical(source)
            return content, "pdf", to_pdf(to_html(content))
        content = render_json(source)
        return content, "json", to_json(content).encode("utf-8")

    def _write_artifact(
        self,
        tenant_id,
        report_type: str,
        period_start: date,
        period_end: date,
        extension: str,
        payload: bytes,
    ) -> str:
        """Write the rendered artifact under REPORT_OUTPUT_DIR; returns file_path."""
        directory = Path(self.output_dir) / str(tenant_id)
        directory.mkdir(parents=True, exist_ok=True)
        rid = report_id(tenant_id, report_type, period_start, period_end)
        filename = (
            f"{report_type}_{period_start.isoformat()}_{period_end.isoformat()}"
            f"_{str(rid)[:8]}.{extension}"
        )
        path = directory / filename
        path.write_bytes(payload)
        return str(path)

    @staticmethod
    def _report_period(decisions: list[Any]) -> tuple[date, date]:
        """The report period: the committed decisions' window, else today."""
        if decisions:
            start = min(d.committed_at.date() for d in decisions)
            end = max(d.committed_at.date() for d in decisions)
            return start, end
        today = datetime.now(UTC).date()
        return today, today

    @staticmethod
    def _summarize(content: dict[str, Any], report_type: str) -> str:
        if report_type == REPORT_TYPE_EXECUTIVE:
            return (
                f"Resumen ejecutivo: {content['decision_count']} decision(es); "
                f"{len(content['top_decisions'])} top; "
                f"{len(content['future_risks'])} riesgo(s) futuro(s); "
                f"{len(content['pending_authority'])} pendiente(s) de autoridad."
            )
        if report_type == REPORT_TYPE_TECHNICAL:
            return (
                f"Informe tecnico: traza cognitiva completa de "
                f"{content['decision_count']} decision(es)."
            )
        return f"Informe JSON: datos de {content['decision_count']} decision(es)."

    def metrics(self) -> dict[str, Any]:
        """Operational metrics (no rule numbers) for /metrics."""
        return {
            "total_reports": self.total_reports,
            "total_report_duplicates": self.total_report_duplicates,
            "total_errors": self.total_errors,
            "reports_by_type": dict(self.by_type),
            "render_duration_seconds": round(self.render_duration_seconds, 6),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
        }