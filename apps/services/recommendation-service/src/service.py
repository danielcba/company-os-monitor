"""Recommendation Service - Action/Propose capability orchestration (R1).

The Propose capability as a service: for each tenant with Hypotheses, it reads
the candidate Hypotheses together with their calibrated Confidence (Sprint 8,
the R4 gate: only hypotheses WITH a calibrated Confidence are considered) and
their Active Context, resolves the explicit Action Space of the scope, runs the
pure Formulator and persists the resulting Recommendations in ``recommendations``
(append-only, idempotent dedup by the deterministic content-addressed id).

This component NEVER writes to ``hypotheses``/``anomalies``/``contexts``/
``evidence``/``observations``/``confidence_scores`` (P1), never reads the
observation bus, never calibrates confidence (R1: exactly one capability -
Propose) and NEVER executes actions or triggers alerts (P6: a Recommendation is
an offer, advisory and reversible; commitment and authority belong to the
Decision layer, Sprint 10).
"""
import asyncio
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from libs.action.recommendation import (
    RecommendationCreate,
    RecommendationStore,
    build_recommendation,
)
from libs.learning.confidence import ConfidenceStore
from libs.perception.context import ContextStore
from libs.procedural_memory.action_space import ActionSpaceEntry
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore

from src.formulator import (
    formulate,
    resolve_active_context,
    resolve_domain,
    select_action_space,
)

# The Hypothesis target the Formulator consumes (calibrated Confidence).
TARGET_TYPE_HYPOTHESIS = "hypothesis"


class RecommendationService:
    """Orchestrates the Propose cycle over each tenant's understanding stream."""

    def __init__(
        self,
        hypothesis_store: HypothesisStore,
        anomaly_store: AnomalyStore,
        context_store: ContextStore,
        confidence_store: ConfidenceStore,
        recommendation_store: RecommendationStore,
        action_space: tuple[ActionSpaceEntry, ...] | list[ActionSpaceEntry],
    ):
        self.hypothesis_store = hypothesis_store
        self.anomaly_store = anomaly_store
        self.context_store = context_store
        self.confidence_store = confidence_store
        self.recommendation_store = recommendation_store
        self.action_space = action_space
        self.total_recommendations = 0
        self.total_duplicates = 0
        self.total_hypotheses_without_confidence = 0
        self.total_hypotheses_without_context = 0
        self.total_hypotheses_without_action_space = 0
        self.errors = 0
        self.by_status: Counter[str] = Counter()
        self.by_domain: Counter[str] = Counter()
        self.last_run_at: datetime | None = None

    async def run_recommendation_cycle(self) -> int:
        """Formulate Recommendations for every tenant with Hypotheses.

        Processes tenants in parallel using asyncio.gather for horizontal
        scalability (each tenant is an independent data domain).
        """
        tenants = await self.hypothesis_store.list_tenant_ids()
        results = await asyncio.gather(
            *[self._formulate_tenant(tenant_id) for tenant_id in tenants],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                self.errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.total_recommendations

    async def _formulate_tenant(self, tenant_id) -> None:
        hypotheses = await self.hypothesis_store.list_hypotheses(tenant_id=tenant_id)
        anomalies = await self.anomaly_store.list_anomalies(tenant_id=tenant_id)
        contexts = await self.context_store.list_contexts(tenant_id=tenant_id)
        for hypothesis in hypotheses:
            # R4 gate: only hypotheses with a calibrated Confidence qualify.
            confidence = await self.confidence_store.get_confidence(
                target_type=TARGET_TYPE_HYPOTHESIS, target_id=hypothesis.id
            )
            if confidence is None:
                self.total_hypotheses_without_confidence += 1
                continue
            context = resolve_active_context(hypothesis, anomalies, contexts)
            if context is None:
                self.total_hypotheses_without_context += 1
                continue
            domain = resolve_domain(context)
            entry = select_action_space(self.action_space, domain, context.purpose)
            if entry is None:
                self.total_hypotheses_without_action_space += 1
                continue
            create = formulate(hypothesis, confidence, context, entry)
            if create is None:
                self.total_hypotheses_without_action_space += 1
                continue
            await self._persist(tenant_id, create, domain)

    async def _persist(
        self, tenant_id, create: RecommendationCreate, domain: str
    ) -> None:
        """Persist one proposed Recommendation (idempotent dedup, never UPDATE)."""
        recommendation = build_recommendation(create)
        row = await self.recommendation_store.save_recommendation(recommendation)
        if row is not None:
            self.total_recommendations += 1
            self.by_status[recommendation.status] += 1
            self.by_domain[domain] += 1
        else:
            self.total_duplicates += 1

    def metrics(self) -> dict[str, Any]:
        """Operational metrics (no rule numbers) for /metrics."""
        return {
            "total_recommendations": self.total_recommendations,
            "total_recommendation_duplicates": self.total_duplicates,
            "total_hypotheses_without_confidence": (
                self.total_hypotheses_without_confidence
            ),
            "total_hypotheses_without_context": self.total_hypotheses_without_context,
            "total_hypotheses_without_action_space": (
                self.total_hypotheses_without_action_space
            ),
            "total_errors": self.errors,
            "recommendations_by_status": dict(self.by_status),
            "recommendations_by_domain": dict(self.by_domain),
        }