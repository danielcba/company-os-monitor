"""Confidence Service - Learning/Calibrate capability orchestration (R1).

The Calibrate capability as a service: reads each tenant's Hypotheses (the
judgments under evaluation) together with their Anomalies, Contexts and
Evidence (the P1 immutable knowledge stream - never raw observations) from
Postgres, computes the calibrated Confidence for every candidate Hypothesis
via the pure calibrator (S + C + ECE + C_final), and persists the rows in
``confidence_scores`` (append-only, idempotent dedup by the deterministic
content-addressed id). It NEVER writes to ``hypotheses``/``anomalies``/
``contexts``/``evidence``/``observations`` (P1) and never reads the observation
bus; it produces no actions (R3) - its output is the transversal input that
enables the Action Layer (R4: every judgment that influences action carries a
confidence score and the reasons for it).

Each persisted row records the score (C_final), the calibration error estimate
(ECE) and the first-class justification (S, C, ECE, alpha, M, L0 - why that
score). In this phase the outcome history is empty (no Memory/outcome store
yet), so the ECE factor is 1.0 (first data, documented); the calibrator already
supports real history for when outcomes arrive.
"""
import asyncio
import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from libs.action.decision import DecisionStore
from libs.cognitive_core.calibration_model import CalibrationParams
from libs.learning.confidence import ConfidenceCreate, ConfidenceStore, build_confidence
from libs.learning.learning_loop import build_learning_history
from libs.perception.context import ContextStore
from libs.perception.evidence import EvidenceStore
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore

from src.calibrator import calibrate, resolve_scope_evidence

log = logging.getLogger(__name__)


class _RunningStats:
    """Welford's online algorithm for mean/variance without storing all values.

    Avoids unbounded memory growth in long-running service.
    """

    def __init__(self, max_samples: int = 1000) -> None:
        self.max_samples = max_samples
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0  # sum of squares of differences from mean

    def add(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (value - self.mean)
        # Optional: cap count to max_samples for sliding window behavior
        # (simpler: just let it grow but memory is O(1) regardless)

    @property
    def mean_value(self) -> float:
        return self.mean if self.count > 0 else 0.0

    def reset(self) -> None:
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0


DEFAULT_BATCH_SIZE = 500


class ConfidenceService:
    """Orchestrates the Calibrate cycle over the tenant knowledge stream."""

    def __init__(
        self,
        hypothesis_store: HypothesisStore,
        anomaly_store: AnomalyStore,
        context_store: ContextStore,
        evidence_store: EvidenceStore,
        confidence_store: ConfidenceStore,
        decision_store: DecisionStore | None = None,
        params: CalibrationParams | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.hypothesis_store = hypothesis_store
        self.anomaly_store = anomaly_store
        self.context_store = context_store
        self.evidence_store = evidence_store
        self.confidence_store = confidence_store
        self.decision_store = decision_store
        self.params = params or CalibrationParams()
        self.batch_size = batch_size
        self.total_confidence_scores = 0
        self.total_duplicates = 0
        self.errors = 0
        self.by_target_type: Counter[str] = Counter()
        self._confidence_stats = _RunningStats()
        self._error_stats = _RunningStats()
        self.last_run_at: datetime | None = None

    async def run_calibration_cycle(self) -> int:
        """Calibrate every candidate Hypothesis of every tenant with Hypotheses."""
        tenants = await self.hypothesis_store.list_tenant_ids()
        # Process tenants in parallel for better throughput
        await asyncio.gather(
            *[self._calibrate_tenant(tenant_id) for tenant_id in tenants],
            return_exceptions=True,
        )
        self.last_run_at = datetime.now(UTC)
        return self.total_confidence_scores

    async def _calibrate_tenant(self, tenant_id) -> None:
        # Process hypotheses in batches to avoid loading all into memory
        offset = 0

        # Load learning history for this tenant (P7 feedback loop).
        # Reads Decisions with actual_outcomes and their Confidence scores
        # to build (confidence, outcome) pairs for ECE computation.
        learning_history = None
        if self.decision_store is not None:
            try:
                decisions = await self.decision_store.list_decisions(
                    tenant_id=tenant_id
                )
                decisions_with_outcomes = [
                    d for d in decisions if d.actual_outcomes
                ]
                if decisions_with_outcomes:
                    all_confidence = await self.confidence_store.list_confidence(
                        tenant_id=tenant_id
                    )
                    learning_history = build_learning_history(
                        tenant_id, decisions_with_outcomes, all_confidence
                    )
            except Exception:
                log.exception(
                    "Failed to load learning history for tenant %s; "
                    "falling back to no-history calibration",
                    tenant_id,
                )

        # Build historical pairs for calibrator: [(confidence, outcome), ...]
        historical = None
        if (
            learning_history is not None
            and learning_history.historical_calibration is not None
        ):
            historical = [
                (p.confidence_score, p.outcome) for p in learning_history.pairs
            ]

        while True:
            hypotheses = await self.hypothesis_store.list_hypotheses(
                tenant_id=tenant_id, limit=self.batch_size, offset=offset
            )
            if not hypotheses:
                break

            # Load anomalies, contexts, evidence once per tenant (could also batch if needed)
            anomalies = await self.anomaly_store.list_anomalies(tenant_id=tenant_id)
            contexts = await self.context_store.list_contexts(tenant_id=tenant_id)
            evidence = await self.evidence_store.list_evidence(tenant_id=tenant_id)
            evidence_by_id = {item.id: item for item in evidence}

            for hypothesis in hypotheses:
                scope = resolve_scope_evidence(
                    hypothesis, anomalies, contexts, evidence_by_id
                )
                # Documented MVP: the hypothesis explains the evidence of its
                # anomaly's contexts; no negative constraints are derived yet, and
                # hypothesis-to-hypothesis consistency is a future sprint.
                coherence_inputs = {
                    "explains": sorted({item.organization_type for item in scope}),
                    "contradicts": [],
                    "coherent_with": [],
                    "incoherent_with": [],
                }
                create = calibrate(
                    hypothesis, evidence, scope, coherence_inputs, self.params, historical
                )
                await self._persist(create)

            offset += self.batch_size

    async def _persist(self, create: ConfidenceCreate) -> None:
        """Persist one calibrated Confidence (idempotent dedup, never an UPDATE)."""
        confidence = build_confidence(create)
        row = await self.confidence_store.save_confidence(confidence)
        if row is not None:
            self.total_confidence_scores += 1
            self.by_target_type[confidence.target_type] += 1
            self._confidence_stats.add(confidence.confidence_score)
            self._error_stats.add(confidence.calibration_error_estimate)
        else:
            self.total_duplicates += 1

    @property
    def mean_confidence_score(self) -> float:
        """Mean C_final over the calibrated judgments (0 when none yet)."""
        return self._confidence_stats.mean_value

    @property
    def mean_calibration_error_estimate(self) -> float:
        """Mean ECE over the calibrated judgments (0 when none yet)."""
        return self._error_stats.mean_value

    def metrics(self) -> dict[str, Any]:
        """Operational metrics (no rule numbers) for /metrics."""
        return {
            "total_confidence_scores": self.total_confidence_scores,
            "total_confidence_duplicates": self.total_duplicates,
            "total_errors": self.errors,
            "confidence_by_target_type": dict(self.by_target_type),
            "mean_confidence_score": self.mean_confidence_score,
            "mean_calibration_error_estimate": self.mean_calibration_error_estimate,
        }