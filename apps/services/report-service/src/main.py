"""Report Service Entry Point - Report Generator (external non-canonical, ADR-0002).

The Report Generator is NOT a cognitive capability: it is a non-canonical
external output (ADR-0002) whose contract is READ the canonical flow -> FORMAT
-> OUTPUT. Per tenant it reads the pipeline tables (decisions, recommendations,
contexts, confidence_scores, hypotheses, anomalies, patterns, evidence,
observations - ALL read-only, P1), renders the requested report_type
(executive/technical/json) with the PURE renderers and persists the row in its
own ``reports`` output table (append-only, idempotent dedup). It NEVER writes
to the cognitive tables (P1) and never reads the observation bus.
"""
import asyncio
import os

from libs.action.decision import DecisionStore
from libs.action.recommendation import RecommendationStore
from libs.action.report import ReportStore
from libs.learning.confidence import ConfidenceStore
from libs.perception.context import ContextStore
from libs.perception.evidence import EvidenceStore
from libs.perception.store import ObservationStore
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore
from libs.reasoning.pattern import PatternStore

from src.health import ReportServer
from src.service import ReportService


async def main():
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("REPORT_HEALTH_PORT", "8098"))
    cycle_seconds = float(os.getenv("REPORT_CYCLE_SECONDS", "60"))
    output_dir = os.getenv("REPORT_OUTPUT_DIR", "reports-output")

    decision_store = DecisionStore(dsn)
    recommendation_store = RecommendationStore(dsn)
    context_store = ContextStore(dsn)
    confidence_store = ConfidenceStore(dsn)
    hypothesis_store = HypothesisStore(dsn)
    anomaly_store = AnomalyStore(dsn)
    pattern_store = PatternStore(dsn)
    evidence_store = EvidenceStore(dsn)
    observation_store = ObservationStore(dsn)
    report_store = ReportStore(dsn)
    for store in (
        decision_store,
        recommendation_store,
        context_store,
        confidence_store,
        hypothesis_store,
        anomaly_store,
        pattern_store,
        evidence_store,
        observation_store,
        report_store,
    ):
        await store.verify_connection()

    service = ReportService(
        decision_store,
        recommendation_store,
        context_store,
        confidence_store,
        hypothesis_store,
        anomaly_store,
        pattern_store,
        evidence_store,
        observation_store,
        report_store,
        output_dir=output_dir,
    )
    server = ReportServer(service)

    await server.start(port)

    while True:
        await service.run_report_cycle()
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())