"""Hypothesis Generator - orchestration of the Predict capability (R1).

Reads each tenant's Anomalies, Contexts and Patterns from Postgres (knowledge -
the Reasoning layer acts on knowledge, never directly on the world), runs the
pure template instantiation over the Hypothesis Template Library, and persists
the candidate Hypotheses in ``hypotheses`` with idempotent dedup. This
component never writes to ``contexts``/``patterns``/``anomalies``/``evidence``/
``observations`` (P1), never reads the observation bus, and never triggers
actions or alerts (R3: cognitive boundary; no action without Confidence, R4).
It only proposes testable candidate explanations - it never confirms or
falsifies them (that requires future evidence + Confidence, Sprint 8).
"""
import asyncio
from collections import Counter
from datetime import UTC, datetime

from libs.perception.context import ContextStore
from libs.procedural_memory.hypothesis_templates import (
    HYPOTHESIS_TEMPLATE_LIBRARY,
    HypothesisTemplate,
)
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import (
    HypothesisStore,
    build_hypothesis,
)
from libs.reasoning.pattern import PatternStore

from src.generator import generate, resolve_anomaly_scope


class HypothesisService:
    def __init__(
        self,
        anomaly_store: AnomalyStore,
        context_store: ContextStore,
        pattern_store: PatternStore,
        hypothesis_store: HypothesisStore,
        templates: tuple[HypothesisTemplate, ...] | list[HypothesisTemplate] = HYPOTHESIS_TEMPLATE_LIBRARY,
    ):
        self.anomaly_store = anomaly_store
        self.context_store = context_store
        self.pattern_store = pattern_store
        self.hypothesis_store = hypothesis_store
        self.templates = templates
        self.total_hypotheses = 0
        self.total_duplicates = 0
        self.total_anomalies_no_templates = 0
        self.errors = 0
        self.by_status: Counter[str] = Counter()
        self.by_mental_model: Counter[str] = Counter()
        self.last_run_at: datetime | None = None

    async def run_generation_cycle(self) -> int:
        """Generate candidate hypotheses for every tenant with an Anomaly stream.

        Processes tenants in parallel using asyncio.gather for horizontal
        scalability (each tenant is an independent data domain).
        """
        tenants = await self.anomaly_store.list_tenant_ids()
        results = await asyncio.gather(
            *[self._generate_tenant(tenant_id) for tenant_id in tenants],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                self.errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.total_hypotheses

    async def _generate_tenant(self, tenant_id) -> None:
        """Generate hypotheses for a single tenant."""
        try:
            anomalies = await self.anomaly_store.list_anomalies(tenant_id=tenant_id)
            contexts = await self.context_store.list_contexts(tenant_id=tenant_id)
            patterns = await self.pattern_store.list_patterns(tenant_id=tenant_id)
            for anomaly in anomalies:
                creations = generate(
                    anomaly,
                    contexts,
                    patterns,
                    library=self.templates,
                )
                scope = resolve_anomaly_scope(anomaly, contexts)
                model_id = scope[0] if scope else "unresolved"
                if not creations:
                    self.total_anomalies_no_templates += 1
                    continue
                for create in creations:
                    await self._persist(tenant_id, create, model_id)
        except Exception:  # noqa: BLE001 - deliberate robustness per repo pattern
            self.errors += 1

    async def _persist(self, tenant_id, create, model_id: str) -> None:
        """Persist one candidate Hypothesis (idempotent dedup, never an UPDATE)."""
        hypothesis = build_hypothesis(create)
        row = await self.hypothesis_store.save_hypothesis(hypothesis)
        if row is not None:
            self.total_hypotheses += 1
            self.by_status[hypothesis.status] += 1
            self.by_mental_model[model_id] += 1
        else:
            self.total_duplicates += 1