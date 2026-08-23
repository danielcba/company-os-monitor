"""Insight Generator - orchestration of the Restructure capability (R1).

Reads each tenant's Hypotheses, Anomalies and Contexts from Postgres
(knowledge - the Reasoning layer acts on knowledge, never directly on the
world), runs the pure rule instantiation over the Insight Rule Library, and
persists the Insights in ``insights`` with idempotent dedup (fully immutable,
P1). This component never writes to ``hypotheses``/``anomalies``/``contexts``/
``evidence``/``observations`` (P1), never reads the observation bus, never
triggers actions or alerts (R3), and never invents facts: Insight restructures
existing knowledge, it is not new information (framework). Restructuring only
happens when the declared rule condition is met - it is never forced or
scheduled.
"""
import asyncio
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from libs.perception.context import ContextStore
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore
from libs.reasoning.insight import InsightStore

from src.generator import generate_insights


class InsightService:
    def __init__(
        self,
        hypothesis_store: HypothesisStore,
        anomaly_store: AnomalyStore,
        context_store: ContextStore,
        insight_store: InsightStore,
    ):
        self.hypothesis_store = hypothesis_store
        self.anomaly_store = anomaly_store
        self.context_store = context_store
        self.insight_store = insight_store
        self.total_insights = 0
        self.total_duplicates = 0
        self.total_frames_non_competitive = 0
        self.errors = 0
        self.by_frame: Counter[str] = Counter()
        self.last_run_at: datetime | None = None

    async def run_restructure_cycle(self) -> int:
        """Generate Insights for every tenant with a Hypothesis stream.

        Processes tenants in parallel using asyncio.gather for horizontal
        scalability (each tenant is an independent data domain).
        """
        tenants = await self.hypothesis_store.list_tenant_ids()
        results = await asyncio.gather(
            *[self._restructure_tenant(tenant_id) for tenant_id in tenants],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                self.errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.total_insights

    async def _restructure_tenant(self, tenant_id) -> None:
        hypotheses = await self.hypothesis_store.list_hypotheses(tenant_id=tenant_id)
        anomalies = await self.anomaly_store.list_anomalies(tenant_id=tenant_id)
        contexts = await self.context_store.list_contexts(tenant_id=tenant_id)
        creations = generate_insights(tenant_id, hypotheses, anomalies, contexts)
        if not creations:
            self.total_frames_non_competitive += 1
            return
        for create in creations:
            await self._persist(tenant_id, create)

    async def _persist(self, tenant_id, create) -> None:
        """Persist one Insight (idempotent dedup, fully immutable - no UPDATE)."""
        from libs.reasoning.insight import build_insight

        insight = build_insight(create)
        row = await self.insight_store.save_insight(insight)
        if row is not None:
            self.total_insights += 1
            frame = (
                create.mental_model_update.get("frame", "unknown")
                if create.mental_model_update is not None
                else "unknown"
            )
            self.by_frame[frame] += 1
        else:
            self.total_duplicates += 1

    def metrics(self) -> dict[str, Any]:
        """Operational metrics (no rule numbers) for /metrics."""
        return {
            "total_insights": self.total_insights,
            "total_insight_duplicates": self.total_duplicates,
            "total_frames_non_competitive": self.total_frames_non_competitive,
            "total_errors": self.errors,
            "insights_by_frame": dict(self.by_frame),
        }