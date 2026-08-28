"""Evaluation Service - Reasoning/Evaluate capability orchestration (R1).

The Evaluate capability as a service: reads each tenant's candidate Hypotheses
together with new Evidence (observations since hypothesis generation), the
calibrated Confidence for each hypothesis, applies the formal Evaluation Policy,
and persists Evaluation records in ``hypothesis_evaluations`` (append-only,
idempotent dedup by deterministic content-addressed id). When evaluation
results in confirmed/falsified, updates the hypothesis status (the only allowed
lifecycle mutation).

This component NEVER writes to previous artifacts
(``hypotheses``/``anomalies``/``contexts``/``evidence``/``observations``/
``confidence_scores`` - P1), never reads the observation bus directly, and
never triggers actions or alerts (R3: cognitive boundary). It only evaluates
existing hypotheses against new evidence.
"""
import asyncio
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from libs.learning.confidence import ConfidenceStore
from libs.perception.evidence import EvidenceStore
from libs.perception.store import ObservationStore
from libs.reasoning.evaluation import EvaluationStore, create_evaluation
from libs.reasoning.evaluation_policy import EvaluationInputs, apply_evaluation_policy
from libs.reasoning.hypothesis import (
    STATUS_CANDIDATE,
    STATUS_CONFIRMED,
    STATUS_FALSIFIED,
    HypothesisStore,
)

DEFAULT_BATCH_SIZE = 500


class EvaluationService:
    """Orchestrates the Evaluate cycle over each tenant's candidate hypotheses."""

    def __init__(
        self,
        hypothesis_store: HypothesisStore,
        observation_store: ObservationStore,
        evidence_store: EvidenceStore,
        confidence_store: ConfidenceStore,
        evaluation_store: EvaluationStore,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.hypothesis_store = hypothesis_store
        self.observation_store = observation_store
        self.evidence_store = evidence_store
        self.confidence_store = confidence_store
        self.evaluation_store = evaluation_store
        self.batch_size = batch_size
        self.total_evaluations = 0
        self.total_duplicates = 0
        self.total_confirmed = 0
        self.total_falsified = 0
        self.total_insufficient = 0
        self.errors = 0
        self.by_result: Counter[str] = Counter()
        self.last_run_at: datetime | None = None

    async def run_evaluation_cycle(self) -> int:
        """Evaluate candidate hypotheses for every tenant.

        Processes tenants in parallel using asyncio.gather for horizontal
        scalability (each tenant is an independent data domain).
        """
        tenants = await self.hypothesis_store.list_tenant_ids()
        results = await asyncio.gather(
            *[self._evaluate_tenant(tenant_id) for tenant_id in tenants],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                self.errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.total_evaluations

    async def _evaluate_tenant(self, tenant_id) -> None:
        """Evaluate candidate hypotheses for a single tenant."""
        try:
            # Get all candidate hypotheses for this tenant
            offset = 0
            while True:
                hypotheses = await self.hypothesis_store.list_hypotheses(
                    tenant_id=tenant_id, limit=self.batch_size, offset=offset
                )
                if not hypotheses:
                    break

                # Filter to only candidate status
                candidates = [h for h in hypotheses if h.status == STATUS_CANDIDATE]
                if not candidates:
                    offset += self.batch_size
                    continue

                # Load new observations since the oldest candidate was generated
                # (In production, this would be more sophisticated - per hypothesis)
                oldest_generated = min(h.generated_at for h in candidates)
                new_observations = await self._get_new_observations(
                    tenant_id, oldest_generated
                )

                # Load confidence scores for all candidates
                confidences = await self._get_confidences_for_hypotheses(
                    tenant_id, candidates
                )

                for hypothesis in candidates:
                    await self._evaluate_hypothesis(
                        tenant_id, hypothesis, new_observations, confidences
                    )

                offset += self.batch_size

        except Exception:  # noqa: BLE001 - deliberate robustness per repo pattern
            self.errors += 1

    async def _get_new_observations(
        self, tenant_id: Any, since: datetime
    ) -> list[dict[str, Any]]:
        """Get new observations for a tenant since a given timestamp.

        Returns structured observations with description for policy matching.
        """
        # Load observations using the store
        observations = await self.observation_store.list_observations_since(
            tenant_id=tenant_id, since=since, limit=1000
        )

        # Convert to structured format for policy
        structured = []
        for obs in observations:
            # Create a description from the fact_type and fact_value for matching
            fact_value = obs["fact_value"]
            desc_parts = [obs["fact_type"]]
            if isinstance(fact_value, dict):
                for k, v in fact_value.items():
                    desc_parts.append(f"{k}={v}")
            structured.append(
                {
                    "id": obs["id"],
                    "source_id": obs["source_id"],
                    "fact_type": obs["fact_type"],
                    "fact_value": fact_value,
                    "unit": obs["unit"],
                    "captured_at": obs["captured_at"],
                    "quality_class": obs["quality_class"],
                    "description": " ".join(desc_parts),
                }
            )
        return structured

    async def _get_confidences_for_hypotheses(
        self, tenant_id: Any, hypotheses: list
    ) -> dict:
        """Get the latest confidence for each candidate hypothesis."""
        confidences = {}
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
                # Keep the most recent (list_confidence returns ordered by computed_at)
                confidences[conf.target_id] = conf
        return confidences

    async def _evaluate_hypothesis(
        self,
        tenant_id: Any,
        hypothesis,
        observations: list[dict[str, Any]],
        confidences: dict,
    ) -> None:
        """Evaluate a single hypothesis against new observations."""
        confidence = confidences.get(hypothesis.id)

        # Build evaluation inputs
        inputs = EvaluationInputs(
            hypothesis=hypothesis,
            new_evidence_observations=observations,
            confidence=confidence,
        )

        # Apply formal evaluation policy
        decision = apply_evaluation_policy(inputs)

        # Persist evaluation
        create = create_evaluation(
            tenant_id=tenant_id,
            hypothesis_id=hypothesis.id,
            evidence_ids=[obs["id"] for obs in observations],
            observed_outcomes=observations,
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
                # Update hypothesis status
                await self.hypothesis_store.update_hypothesis_status(
                    tenant_id=tenant_id, hypothesis_id=hypothesis.id, status=STATUS_CONFIRMED
                )
            elif decision.result == STATUS_FALSIFIED:
                self.total_falsified += 1
                await self.hypothesis_store.update_hypothesis_status(
                    tenant_id=tenant_id, hypothesis_id=hypothesis.id, status=STATUS_FALSIFIED
                )
            else:
                self.total_insufficient += 1
        else:
            self.total_duplicates += 1

    def metrics(self) -> dict[str, Any]:
        """Operational metrics for /metrics."""
        return {
            "total_evaluations": self.total_evaluations,
            "total_evaluation_duplicates": self.total_duplicates,
            "total_confirmed": self.total_confirmed,
            "total_falsified": self.total_falsified,
            "total_insufficient": self.total_insufficient,
            "total_errors": self.errors,
            "evaluations_by_result": dict(self.by_result),
        }