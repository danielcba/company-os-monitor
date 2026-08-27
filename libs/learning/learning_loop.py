"""Learning Loop — P7 feedback mechanism (Learning-family read/compute).

Closes the cognitive loop by computing historical calibration data from
Decision outcomes and feeding it back into Confidence calibration.

The framework (P7): "The comparison of expected and actual outcomes is the
primary input to the Confidence calibration model." This module computes
that comparison as (confidence_score, outcome) pairs for ECE estimation.

R1: single capability — computes learning signal from executed Decisions.
    Does not calibrate, decide, or execute.
P1: reads immutable Decision and Confidence rows; never writes.
ADR-0002: external read/compute capability built on canonical stores.
P7: closes the learning loop — the system improves from its outcomes.
"""
from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from libs.cognitive_core.calibration_model import CalibrationParams, ece_score


def compute_outcome_signal(decision: Any) -> int | None:
    """Determine if a Decision's expected outcomes were met (1) or not (0).

    Returns None when the outcome cannot be determined (inconclusive):
    no actual_outcomes, no expected_outcomes, or no matchable metrics.

    Follows the no-fabrication principle (P1): missing or unparseable
    actuals never produce a failure signal — they produce None (inconclusive).
    """
    expected: list[dict[str, Any]] = decision.expected_outcomes or []
    actuals = decision.actual_outcomes
    if not actuals or not expected:
        return None

    actual_by_metric: dict[str, dict[str, Any]] = {}
    for ao in actuals:
        if isinstance(ao, dict):
            metric = ao.get("verifiable_by")
            if metric is not None:
                actual_by_metric[str(metric)] = ao

    corroborated = 0
    contradicted = 0
    PREDICTION_THRESHOLD = 0.5

    for eo in expected:
        if not isinstance(eo, dict):
            continue
        metric = eo.get("verifiable_by")
        if metric is None or str(metric) not in actual_by_metric:
            continue

        raw_pred = eo.get("predictiction", eo.get("prediction", ""))
        try:
            pred = float(raw_pred)
        except (ValueError, TypeError):
            pred = 0.0
        predicted_positive = pred >= PREDICTION_THRESHOLD

        actual = actual_by_metric[str(metric)]
        actual_value = actual.get("value") if isinstance(actual, dict) else None
        binary = _to_binary(actual_value)
        if binary is None:
            continue

        correct = (predicted_positive and binary == 1) or (
            not predicted_positive and binary == 0
        )
        if correct:
            corroborated += 1
        else:
            contradicted += 1

    matched = corroborated + contradicted
    if matched == 0:
        return None
    return 1 if corroborated > contradicted else 0


def _to_binary(value: Any) -> int | None:
    """Map an actual outcome value to binary success (1) / failure (0)."""
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


class LearningSignal(BaseModel):
    """One (confidence, outcome) pair for ECE computation."""

    confidence_score: float
    outcome: int  # 0 or 1
    decision_id: uuid.UUID
    tenant_id: uuid.UUID

    model_config = ConfigDict(frozen=True)


class LearningHistory(BaseModel):
    """Aggregated historical calibration data for a tenant."""

    tenant_id: uuid.UUID
    total_decisions_with_outcomes: int
    pairs: list[LearningSignal]
    ece: float | None = None
    historical_calibration: float | None = None  # 1 - ECE

    model_config = ConfigDict(frozen=True)


@runtime_checkable
class DecisionReader(Protocol):
    """Reads Decisions (injectable for tests)."""

    async def list_decisions(self, *, tenant_id: uuid.UUID) -> list[Any]:
        ...


@runtime_checkable
class ConfidenceScoreReader(Protocol):
    """Reads Confidence scores by id (injectable for tests)."""

    async def list_confidence(
        self, *, tenant_id: uuid.UUID, limit: int = 500, offset: int = 0
    ) -> list[Any]:
        ...


def build_learning_history(
    tenant_id: uuid.UUID,
    decisions: list[Any],
    confidence_scores: list[Any],
) -> LearningHistory:
    """Build historical calibration data from Decisions and Confidence scores.

    Pure, no IO: takes pre-loaded data and computes (confidence, outcome) pairs.
    The caller is responsible for loading the data from the stores.

    Returns a LearningHistory with pairs and ECE. If fewer than 2 pairs are
    available, ECE is None (not enough data for meaningful calibration).
    """
    confidence_by_id: dict[uuid.UUID, Any] = {c.id: c for c in confidence_scores}

    pairs: list[LearningSignal] = []
    for decision in decisions:
        outcome = compute_outcome_signal(decision)
        if outcome is None:
            continue

        confidence = confidence_by_id.get(decision.confidence_id)
        if confidence is None:
            continue

        pairs.append(
            LearningSignal(
                confidence_score=confidence.confidence_score,
                outcome=outcome,
                decision_id=decision.id,
                tenant_id=tenant_id,
            )
        )

    ece = None
    hist_cal = None
    min_pairs_for_ece = 2
    if len(pairs) >= min_pairs_for_ece:
        predictions = [p.confidence_score for p in pairs]
        outcomes = [p.outcome for p in pairs]
        ece = round(ece_score(predictions, outcomes, CalibrationParams().M), 4)
        hist_cal = round(max(0.0, min(1.0, 1.0 - ece)), 4)

    return LearningHistory(
        tenant_id=tenant_id,
        total_decisions_with_outcomes=len(pairs),
        pairs=pairs,
        ece=ece,
        historical_calibration=hist_cal,
    )
