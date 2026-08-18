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
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from libs.cognitive_core.calibration_model import CalibrationParams
from libs.learning.confidence import ConfidenceCreate, ConfidenceStore, build_confidence
from libs.perception.context import ContextStore
from libs.perception.evidence import EvidenceStore
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore

from src.calibrator import calibrate, resolve_scope_evidence


class ConfidenceService:
    """Orchestrates the Calibrate cycle over the tenant knowledge stream."""

    def __init__(
        self,
        hypothesis_store: HypothesisStore,
        anomaly_store: AnomalyStore,
        context_store: ContextStore,
        evidence_store: EvidenceStore,
        confidence_store: ConfidenceStore,
        params: CalibrationParams | None = None,
    ):
        self.hypothesis_store = hypothesis_store
        self.anomaly_store = anomaly_store
        self.context_store = context_store
        self.evidence_store = evidence_store
        self.confidence_store = confidence_store
        self.params = params or CalibrationParams()
        self.total_confidence_scores = 0
        self.total_duplicates = 0
        self.errors = 0
        self.by_target_type: Counter[str] = Counter()
        self.confidence_values: list[float] = []
        self.error_estimates: list[float] = []
        self.last_run_at: datetime | None = None

    async def run_calibration_cycle(self) -> int:
        """Calibrate every candidate Hypothesis of every tenant with Hypotheses."""
        tenants = await self.hypothesis_store.list_tenant_ids()
        for tenant_id in tenants:
            try:
                await self._calibrate_tenant(tenant_id)
            except Exception:  # noqa: BLE001 - deliberate robustness per repo pattern
                self.errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.total_confidence_scores

    async def _calibrate_tenant(self, tenant_id) -> None:
        hypotheses = await self.hypothesis_store.list_hypotheses(tenant_id=tenant_id)
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
                hypothesis, evidence, coherence_inputs, self.params, None
            )
            await self._persist(create)

    async def _persist(self, create: ConfidenceCreate) -> None:
        """Persist one calibrated Confidence (idempotent dedup, never an UPDATE)."""
        confidence = build_confidence(create)
        row = await self.confidence_store.save_confidence(confidence)
        if row is not None:
            self.total_confidence_scores += 1
            self.by_target_type[confidence.target_type] += 1
            self.confidence_values.append(confidence.confidence_score)
            self.error_estimates.append(confidence.calibration_error_estimate)
        else:
            self.total_duplicates += 1

    @property
    def mean_confidence_score(self) -> float:
        """Mean C_final over the calibrated judgments (0 when none yet)."""
        if not self.confidence_values:
            return 0.0
        return sum(self.confidence_values) / len(self.confidence_values)

    @property
    def mean_calibration_error_estimate(self) -> float:
        """Mean ECE over the calibrated judgments (0 when none yet)."""
        if not self.error_estimates:
            return 0.0
        return sum(self.error_estimates) / len(self.error_estimates)

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