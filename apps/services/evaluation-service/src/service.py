"""Evaluation Service - Reasoning/Evaluate capability orchestration (R1).

The Evaluate capability as a service: reads each tenant's candidate Hypotheses
together with new **Evidence** (the structured knowledge produced by Perception
since the hypothesis was generated), the calibrated Confidence for each
hypothesis, applies the formal Evaluation Policy, and persists Evaluation records
in ``hypothesis_evaluations`` (append-only, idempotent dedup by deterministic
content-addressed id). When evaluation results in confirmed/falsified on a
reliable evidence basis, it updates the hypothesis status (the only allowed
lifecycle mutation).

Architectural boundary (R3/R7):
- This component NEVER reads the Observation store directly. It consumes the
  canonical Perception artifact (Evidence). Observations are Perception's raw
  capture; Evidence is the organized knowledge that Reasoning is allowed to act
  on (Observation -> Evidence -> Context -> ... -> Hypothesis -> Evaluation).
- It NEVER writes to previous artifacts (``hypotheses``/``anomalies``/
  ``contexts``/``evidence``/``observations``/``confidence_scores`` - P1), never
  triggers actions or alerts (R3: cognitive boundary). It only evaluates
  existing hypotheses against new evidence.
"""
import asyncio
import os
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from libs.learning.confidence import ConfidenceStore
from libs.perception.evidence import EvidenceStore
from libs.reasoning.evaluation import EvaluationStore, create_evaluation
from libs.reasoning.evaluation_policy import EvaluationInputs, apply_evaluation_policy
from libs.reasoning.hypothesis import (
    STATUS_CANDIDATE,
    STATUS_CONFIRMED,
    STATUS_FALSIFIED,
    HypothesisStore,
)

DEFAULT_BATCH_SIZE = 500
# Bounded concurrency over tenants (P9: avoid unbounded asyncio.gather fan-out and
# DB connection exhaustion). A single gather over all tenants is not automatically
# scalable.
MAX_CONCURRENT_TENANTS = int(os.environ.get("EVALUATION_MAX_TENANTS", "8"))


class EvaluationService:
    """Orchestrates the Evaluate cycle over each tenant's candidate hypotheses."""

    def __init__(
        self,
        hypothesis_store: HypothesisStore,
        evidence_store: EvidenceStore,
        confidence_store: ConfidenceStore,
        evaluation_store: EvaluationStore,
        batch_size: int = DEFAULT_BATCH_SIZE,
        # The MVP matcher is heuristic (textual over Evidence descriptions), so the
        # service must NOT auto-promote a Hypothesis to a terminal state on it.
        # A future reliable/structured evidence basis flips this to True.
        evidence_basis_reliable: bool = False,
        max_concurrent_tenants: int = MAX_CONCURRENT_TENANTS,
    ):
        self.hypothesis_store = hypothesis_store
        self.evidence_store = evidence_store
        self.confidence_store = confidence_store
        self.evaluation_store = evaluation_store
        self.batch_size = batch_size
        self.evidence_basis_reliable = evidence_basis_reliable
        self._tenant_semaphore = asyncio.Semaphore(max_concurrent_tenants)
        self.total_evaluations = 0
        self.total_duplicates = 0
        self.total_confirmed = 0
        self.total_falsified = 0
        self.total_insufficient = 0
        self.errors = 0
        self.evaluation_cycles = 0
        self.last_successful_cycle_at: datetime | None = None
        self.by_result: Counter[str] = Counter()

    async def run_evaluation_cycle(self) -> int:
        """Evaluate candidate hypotheses for every tenant.

        Tenants are discovered from the canonical source (hypotheses table), so a
        tenant that has candidate hypotheses but zero evaluations yet is still
        discovered and evaluated. Tenant processing runs with bounded concurrency.
        """
        tenants = await self.hypothesis_store.list_tenant_ids()
        if not tenants:
            self.evaluation_cycles += 1
            self.last_successful_cycle_at = datetime.now(UTC)
            return 0

        async def _guarded(tenant_id: Any) -> None:
            async with self._tenant_semaphore:
                await self._evaluate_tenant(tenant_id)

        results = await asyncio.gather(
            *[_guarded(t) for t in tenants], return_exceptions=True
        )
        # Exceptions escaping the tenant guard are real failures (e.g. DB down);
        # they are distinguishable from a clean "zero hypotheses evaluated" run.
        for result in results:
            if isinstance(result, Exception):
                self.errors += 1

        self.evaluation_cycles += 1
        if self.errors == 0 or any(
            isinstance(r, type(None)) for r in results
        ):
            self.last_successful_cycle_at = datetime.now(UTC)
        return self.total_evaluations

    async def _evaluate_tenant(self, tenant_id) -> None:
        """Evaluate candidate hypotheses for a single tenant."""
        try:
            offset = 0
            while True:
                hypotheses = await self.hypothesis_store.list_hypotheses(
                    tenant_id=tenant_id, limit=self.batch_size, offset=offset
                )
                if not hypotheses:
                    break

                candidates = [h for h in hypotheses if h.status == STATUS_CANDIDATE]
                if not candidates:
                    offset += self.batch_size
                    continue

                # Only the knowledge produced after the oldest candidate was
                # generated is relevant (canonical Evidence, not raw Observations).
                oldest_generated = min(h.generated_at for h in candidates)
                new_evidence = await self._get_new_evidence(
                    tenant_id, oldest_generated
                )

                confidences = await self._get_confidences_for_hypotheses(
                    tenant_id, candidates
                )

                for hypothesis in candidates:
                    await self._evaluate_hypothesis(
                        tenant_id, hypothesis, new_evidence, confidences
                    )

                offset += self.batch_size
        except Exception:  # noqa: BLE001 - tenant-level failure must not kill the cycle
            self.errors += 1
            raise

    async def _get_new_evidence(
        self, tenant_id: Any, since: datetime
    ) -> list:
        """Load new Evidence for a tenant since a given timestamp.

        Returns canonical Evidence artifacts (never raw Observations).
        """
        return await self.evidence_store.list_evidence_since(
            tenant_id=tenant_id, since=since
        )

    async def _get_confidences_for_hypotheses(
        self, tenant_id: Any, hypotheses: list
    ) -> dict:
        """Get the latest confidence for each candidate hypothesis."""
        confidences: dict[Any, Any] = {}
        all_confidence = await self.confidence_store.list_confidence(
            tenant_id=tenant_id
        )
        hypothesis_ids = {h.id for h in hypotheses}
        for conf in all_confidence:
            if (
                conf.target_type == "hypothesis"
                and conf.target_id in hypothesis_ids
                and conf.target_id not in confidences
            ):
                confidences[conf.target_id] = conf
        return confidences

    async def _evaluate_hypothesis(
        self,
        tenant_id: Any,
        hypothesis,
        evidence: list,
        confidences: dict,
    ) -> None:
        """Evaluate a single hypothesis against new Evidence."""
        confidence = confidences.get(hypothesis.id)

        inputs = EvaluationInputs(
            hypothesis=hypothesis,
            evidence=evidence,
            confidence=confidence,
            evidence_basis_reliable=self.evidence_basis_reliable,
        )

        decision = apply_evaluation_policy(inputs)

        observed_outcomes = [
            {
                "evidence_id": str(ev.id),
                "organization_type": ev.organization_type,
                "description": ev.description,
                "quality_class": ev.quality_class.value
                if hasattr(ev.quality_class, "value")
                else str(ev.quality_class),
            }
            for ev in evidence
        ]

        create = create_evaluation(
            tenant_id=tenant_id,
            hypothesis_id=hypothesis.id,
            evidence_ids=[ev.id for ev in evidence],
            observed_outcomes=observed_outcomes,
            support_count=decision.support_count,
            contradiction_count=decision.contradiction_count,
            confidence_id=confidence.id if confidence else None,
            result=decision.result,
            rationale=decision.rationale,
        )
        row = await self.evaluation_store.save_evaluation(create)
        if row is not None:
            self.total_evaluations += 1
            self.by_result[decision.result] += 1
            if decision.result == STATUS_CONFIRMED:
                self.total_confirmed += 1
                await self.hypothesis_store.update_hypothesis_status(
                    tenant_id=tenant_id,
                    hypothesis_id=hypothesis.id,
                    status=STATUS_CONFIRMED,
                )
            elif decision.result == STATUS_FALSIFIED:
                self.total_falsified += 1
                await self.hypothesis_store.update_hypothesis_status(
                    tenant_id=tenant_id,
                    hypothesis_id=hypothesis.id,
                    status=STATUS_FALSIFIED,
                )
            else:
                self.total_insufficient += 1
        else:
            self.total_duplicates += 1

    def metrics(self) -> dict[str, Any]:
        """Operational metrics for /metrics."""
        return {
            "evaluation_cycles": self.evaluation_cycles,
            "total_evaluations": self.total_evaluations,
            "total_evaluation_duplicates": self.total_duplicates,
            "total_confirmed": self.total_confirmed,
            "total_falsified": self.total_falsified,
            "total_insufficient": self.total_insufficient,
            "total_errors": self.errors,
            "last_successful_cycle_at": (
                self.last_successful_cycle_at.isoformat()
                if self.last_successful_cycle_at
                else None
            ),
            "evaluations_by_result": dict(self.by_result),
        }
