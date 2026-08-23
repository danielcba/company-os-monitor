"""Decision Service - Action/Commit capability orchestration (R1).

The Commit capability as a service: for each tenant with proposed
Recommendations, it reads the proposed Recommendations together with the
calibrated Confidence bound to each (R4: every Decision carries Confidence), the
explicit Decision Policy of the domain (procedural memory) and the commitment
Authority, runs the pure Committer and persists the committed Decisions in
``decisions`` (append-only, idempotent dedup by the deterministic
content-addressed id).

This component NEVER writes to previous artifacts
(``recommendations``/``hypotheses``/``anomalies``/``contexts``/``evidence``/
``observations``/``confidence_scores`` - P1), never reads the observation bus,
never calibrates confidence and never forms recommendations (R1: exactly one
capability - Commit) and NEVER executes real-world actions or triggers alerts
(P6: the Decision is recorded with its falsifiable expected outcomes; execution
and authorization are future phases). ``executed_at``/``actual_outcomes`` stay
NULL: the expected vs actual comparison is the Learning loop (P7, future).
"""
import asyncio
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from libs.action.decision import DecisionStore, build_decision
from libs.action.recommendation import STATUS_PROPOSED, RecommendationStore
from libs.learning.confidence import ConfidenceStore
from libs.procedural_memory.decision_policy import (
    POLICY_BY_DOMAIN,
    DecisionPolicyEntry,
    apply_threshold_overrides,
    select_policy,
)

from src.committer import (
    BELOW_CONFIDENCE,
    COMMITTABLE,
    NO_AUTHORITY,
    NO_POLICY,
    RISK_NOT_ALLOWED,
    Authority,
    commit,
    commit_eligibility,
    policy_authority_id,
    recommendation_domain,
    resolve_risk_tolerance,
)

# Eligibility reasons that skip a Recommendation without committing.
_SKIP_REASONS: frozenset[str] = frozenset(
    {BELOW_CONFIDENCE, RISK_NOT_ALLOWED, NO_AUTHORITY, NO_POLICY}
)


class DecisionService:
    """Orchestrates the Commit cycle over each tenant's proposed offers."""

    def __init__(
        self,
        recommendation_store: RecommendationStore,
        confidence_store: ConfidenceStore,
        decision_store: DecisionStore,
        min_confidence_for_commit: float = 0.75,
        min_confidence_irreversible: float = 0.9,
    ):
        self.recommendation_store = recommendation_store
        self.confidence_store = confidence_store
        self.decision_store = decision_store
        self.min_confidence_for_commit = min_confidence_for_commit
        self.min_confidence_irreversible = min_confidence_irreversible
        self.total_decisions = 0
        self.total_duplicates = 0
        self.total_recommendations_below_confidence = 0
        self.total_recommendations_skipped = 0
        self.errors = 0
        self.by_status: Counter[str] = Counter()
        self.by_risk_tolerance: Counter[str] = Counter()
        self.last_run_at: datetime | None = None

    async def run_decision_cycle(self) -> int:
        """Commit Decisions for every tenant with proposed Recommendations.

        Processes tenants in parallel using asyncio.gather for horizontal
        scalability (each tenant is an independent data domain).
        """
        tenants = await self.recommendation_store.list_tenant_ids()
        results = await asyncio.gather(
            *[self._commit_tenant(tenant_id) for tenant_id in tenants],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                self.errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.total_decisions

    async def _commit_tenant(self, tenant_id) -> None:
        recommendations = await self.recommendation_store.list_recommendations(
            tenant_id=tenant_id
        )
        confidences = {
            confidence.id: confidence
            for confidence in await self.confidence_store.list_confidence(
                tenant_id=tenant_id
            )
        }
        for recommendation in recommendations:
            if recommendation.status != STATUS_PROPOSED:
                continue
            confidence = confidences.get(recommendation.confidence_id)
            if confidence is None:
                self.total_recommendations_skipped += 1
                continue
            policy = self._policy_for(recommendation)
            if policy is None:
                self.total_recommendations_skipped += 1
                continue
            risk = resolve_risk_tolerance(confidence.confidence_score, policy)
            if risk is None:
                self.total_recommendations_below_confidence += 1
                continue
            authority = Authority(
                authority_id=policy_authority_id(policy.policy_id),
                label=f"policy:{policy.policy_id}",
                risk_tolerance=risk,
            )
            reason = commit_eligibility(
                recommendation, confidence, policy, authority
            )
            if reason != COMMITTABLE:
                if reason == BELOW_CONFIDENCE:
                    self.total_recommendations_below_confidence += 1
                else:
                    self.total_recommendations_skipped += 1
                continue
            await self._persist(recommendation, confidence, policy, authority)

    def _policy_for(self, recommendation) -> DecisionPolicyEntry | None:
        """The Decision Policy of the recommendation's domain (with overrides)."""
        domain = recommendation_domain(recommendation)
        policy = select_policy(POLICY_BY_DOMAIN, domain)
        if policy is None:
            return None
        return apply_threshold_overrides(
            policy,
            self.min_confidence_for_commit,
            self.min_confidence_irreversible,
        )

    async def _persist(
        self,
        recommendation,
        confidence,
        policy: DecisionPolicyEntry,
        authority: Authority,
    ) -> None:
        """Persist one committed Decision (idempotent dedup, never UPDATE)."""
        create = commit(recommendation, confidence, policy, authority)
        if create is None:
            self.total_recommendations_skipped += 1
            return
        decision = build_decision(create)
        row = await self.decision_store.save_decision(decision)
        if row is not None:
            self.total_decisions += 1
            self.by_status[decision.status] += 1
            self.by_risk_tolerance[decision.risk_tolerance] += 1
        else:
            self.total_duplicates += 1

    def metrics(self) -> dict[str, Any]:
        """Operational metrics (no rule numbers) for /metrics."""
        return {
            "total_decisions": self.total_decisions,
            "total_decision_duplicates": self.total_duplicates,
            "total_recommendations_below_confidence": (
                self.total_recommendations_below_confidence
            ),
            "total_recommendations_skipped": self.total_recommendations_skipped,
            "total_errors": self.errors,
            "decisions_by_status": dict(self.by_status),
            "decisions_by_risk_tolerance": dict(self.by_risk_tolerance),
        }