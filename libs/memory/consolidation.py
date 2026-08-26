"""Memory Layer — Outcome Consolidation (P7, Learning-family read/compute).

The Cognitive Architecture defines the Memory Layer as the stratified store
that consolidates Observations, Decisions and Outcomes to support Confidence
calibration and enable Learning through comparison of expected vs actual
outcomes (core-concepts / cognitive-architecture.md: "Learning is not a phase.
It is a continuous loop.").

This module implements the **Outcome Consolidation** capability as a COMPUTED,
tenant-scoped, read-only layer over the canonical Decision store. It is a
single cognitive capability (R1): given committed Decisions (which already
record falsifiable ``expected_outcomes`` BEFORE execution) and any recorded
``actual_outcomes`` (a lifecycle field populated by the Learning loop), it
compares them and produces a calibration signal.

It rigorously follows the framework:

- **P1 (Primacy of Observation / no fabrication)**: a Decision with NO
  ``actual_outcomes`` yields an *inconclusive* consolidation — missing outcomes
  are NEVER treated as failure. We never invent observations or outcomes.
- **R1 (exactly one capability)**: this module only consolidates outcomes; it
  does not calibrate, decide, or execute.
- **R7 (architecture guides code)**: it reads canonical stores; it does not
  reimplement cognitive logic.
- **ADR-0002 (external, non-canonical scope)**: consolidation is an external
  read/compute capability built on top of canonical artifacts; it does NOT
  create a new persisted entity (Memory persistence remains planned per the
  framework). No new table, no new id, no mutation.
- **Tenant scope**: every consolidation is anchored to one ``tenant_id``; a
  cross-tenant input is rejected (defense in depth on top of the gateway's
  own tenant isolation).
"""
from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from libs.action.decision import Decision
from libs.cognitive_core.calibration_model import (
    CalibrationParams,
    brier_score,
    ece_score,
)

# A prediction >= this threshold is treated as "positive" (success expected);
# a prediction < threshold is "negative" (no success expected). Mirrors the
# Decision module's PREDICTION_THRESHOLD.
PREDICTION_THRESHOLD = 0.5


class TenantScopeError(Exception):
    """Raised when a consolidation receives decisions outside the tenant scope."""


class CrossTenantConsolidationError(TenantScopeError):
    """A decision in the batch belongs to a different tenant than requested."""

    @classmethod
    def for_decision(
        cls,
        decision_id: uuid.UUID,
        owner: uuid.UUID,
        requested: uuid.UUID,
    ) -> CrossTenantConsolidationError:
        return cls(
            f"decision {decision_id} belongs to tenant {owner}, "
            f"not requested tenant {requested}"
        )


def _to_binary(value: Any) -> int | None:
    """Map an actual outcome value to a binary success (1) / failure (0).

    Returns None when the value cannot be interpreted (so the outcome is
    reported as inconclusive rather than fabricated as a failure).
    """
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "success", "ok", "yes", "1"):
            return 1
        if low in ("false", "failure", "fail", "no", "0", ""):
            return 0
    return None


class ConsolidationResult(BaseModel):
    """Per-Decision consolidation (read/compute; never persisted).

    ``calibration_feedback`` is bounded in [-1, 1]: +1 when every matched
    outcome corroborated the prediction, -1 when every matched outcome
    contradicted it, 0 when there is nothing to learn from yet. Missing
    actuals never contribute a negative signal (P1: no fabrication).
    """

    decision_id: uuid.UUID
    tenant_id: uuid.UUID
    has_actuals: bool
    expected_count: int
    actual_count: int
    corroborated: int
    contradicted: int
    inconclusive: int
    calibration_feedback: float
    brier: float | None = None
    ece: float | None = None
    details: list[dict[str, Any]] = []

    model_config = ConfigDict(frozen=True)


class ConsolidationReport(BaseModel):
    """Tenant-scoped aggregate of consolidated Decisions (read/compute)."""

    tenant_id: uuid.UUID
    total_decisions: int
    decisions_with_actuals: int
    corroborated: int
    contradicted: int
    inconclusive: int
    aggregate_feedback: float
    brier: float | None = None
    ece: float | None = None
    results: list[ConsolidationResult] = []

    model_config = ConfigDict(frozen=True)


def _classify_expected_outcome(
    eo: dict[str, Any],
    actual_by_metric: dict[str, dict[str, Any]],
    threshold: float,
) -> tuple[int, int, int, dict[str, Any]]:
    """Classify one expected outcome against recorded actuals.

    Returns (corroborated, contradicted, inconclusive, detail). Missing or
    unparseable actuals yield ``inconclusive`` — never a fabricated failure
    (P1: no fabrication).
    """
    metric = eo.get("verifiable_by")
    raw_pred = eo.get("predictiction", eo.get("prediction", ""))
    try:
        pred = float(raw_pred)
    except (ValueError, TypeError):
        pred = 0.0
    predicted_positive = pred >= threshold

    if metric is None or str(metric) not in actual_by_metric:
        return 0, 0, 1, {
            "metric": str(metric) if metric is not None else None,
            "prediction": round(pred, 4),
            "classification": "inconclusive",
            "reason": "no_actual_outcome",
        }

    actual = actual_by_metric[str(metric)]
    actual_value = actual.get("value") if isinstance(actual, dict) else None
    binary = _to_binary(actual_value)
    if binary is None:
        return 0, 0, 1, {
            "metric": str(metric),
            "prediction": round(pred, 4),
            "classification": "inconclusive",
            "reason": "actual_unparseable",
        }

    correct = (predicted_positive and binary == 1) or (
        not predicted_positive and binary == 0
    )
    classification = "corroborated" if correct else "contradicted"
    return (1 if correct else 0), (0 if correct else 1), 0, {
        "metric": str(metric),
        "prediction": round(pred, 4),
        "actual": binary,
        "classification": classification,
    }


def build_consolidation(decision: Decision) -> ConsolidationResult:
    """Consolidate one Decision's expected vs actual outcomes (pure, no IO)."""
    expected: list[dict[str, Any]] = decision.expected_outcomes or []
    actuals = decision.actual_outcomes
    has_actuals = bool(actuals)
    actual_count = len(actuals) if actuals else 0

    actual_by_metric: dict[str, dict[str, Any]] = {}
    if actuals:
        for ao in actuals:
            if isinstance(ao, dict):
                metric = ao.get("verifiable_by")
                if metric is not None:
                    actual_by_metric[str(metric)] = ao

    corroborated = 0
    contradicted = 0
    inconclusive = 0
    details: list[dict[str, Any]] = []
    predictions: list[float] = []
    outcomes: list[int] = []

    for eo in expected:
        if not isinstance(eo, dict):
            inconclusive += 1
            details.append(
                {"metric": None, "prediction": None, "classification": "inconclusive"}
            )
            continue

        corr, contr, incon, detail = _classify_expected_outcome(
            eo, actual_by_metric, PREDICTION_THRESHOLD
        )
        corroborated += corr
        contradicted += contr
        inconclusive += incon
        details.append(detail)
        if detail["classification"] in ("corroborated", "contradicted"):
            predictions.append(float(detail["prediction"]))
            outcomes.append(int(detail["actual"]))

    matched = corroborated + contradicted
    calibration_feedback = (corroborated - contradicted) / matched if matched > 0 else 0.0

    brier = round(brier_score(predictions, outcomes), 4) if predictions else None
    ece = (
        round(ece_score(predictions, outcomes, CalibrationParams().M), 4)
        if predictions
        else None
    )

    return ConsolidationResult(
        decision_id=decision.id,
        tenant_id=decision.tenant_id,
        has_actuals=has_actuals,
        expected_count=len(expected),
        actual_count=actual_count,
        corroborated=corroborated,
        contradicted=contradicted,
        inconclusive=inconclusive,
        calibration_feedback=round(calibration_feedback, 4),
        brier=brier,
        ece=ece,
        details=details,
    )


def consolidate_decisions(
    tenant_id: uuid.UUID, decisions: list[Decision]
) -> ConsolidationReport:
    """Consolidate a tenant-scoped batch of Decisions (read/compute).

    Raises CrossTenantConsolidationError if any decision belongs to a different
    tenant — consolidation never leaks or mixes tenants (defense in depth).
    """
    for decision in decisions:
        if decision.tenant_id != tenant_id:
            raise CrossTenantConsolidationError.for_decision(
                decision.id, decision.tenant_id, tenant_id
            )

    results = [build_consolidation(d) for d in decisions]

    corroborated = sum(r.corroborated for r in results)
    contradicted = sum(r.contradicted for r in results)
    inconclusive = sum(r.inconclusive for r in results)
    with_actuals = sum(1 for r in results if r.has_actuals)

    matched = corroborated + contradicted
    agg_feedback = (corroborated - contradicted) / matched if matched > 0 else 0.0

    all_preds: list[float] = []
    all_outcomes: list[int] = []
    for r in results:
        for d in r.details:
            cls = d.get("classification")
            if cls in ("corroborated", "contradicted"):
                all_preds.append(float(d["prediction"]))
                all_outcomes.append(int(d["actual"]))

    agg_brier = round(brier_score(all_preds, all_outcomes), 4) if all_preds else None
    agg_ece = (
        round(ece_score(all_preds, all_outcomes, CalibrationParams().M), 4)
        if all_preds
        else None
    )

    return ConsolidationReport(
        tenant_id=tenant_id,
        total_decisions=len(results),
        decisions_with_actuals=with_actuals,
        corroborated=corroborated,
        contradicted=contradicted,
        inconclusive=inconclusive,
        aggregate_feedback=round(agg_feedback, 4),
        brier=agg_brier,
        ece=agg_ece,
        results=results,
    )


@runtime_checkable
class DecisionReader(Protocol):
    """Minimal reader the ConsolidationStore needs (injectable for tests)."""

    async def list_decisions(self, *, tenant_id: uuid.UUID) -> list[Decision]:
        ...


@runtime_checkable
class ConsolidationStoreProtocol(Protocol):
    """External read/compute store contract (ADR-0002)."""

    async def consolidate_for_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> ConsolidationReport:
        ...


class ConsolidationStore:
    """Read/compute store: consolidates a tenant's Decisions on demand.

    Wraps a DecisionReader (the canonical Decision store in production) and
    applies the pure consolidation transform. It performs NO writes and creates
    NO new entity (Memory persistence remains planned per the framework).
    """

    def __init__(self, decision_store: DecisionReader):
        self._decision_store = decision_store

    async def consolidate_for_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> ConsolidationReport:
        decisions = await self._decision_store.list_decisions(tenant_id=tenant_id)
        return consolidate_decisions(tenant_id, decisions)

    async def verify_connection(self) -> None:
        if hasattr(self._decision_store, "verify_connection"):
            await self._decision_store.verify_connection()
