"""Hypothesis Evaluation Policy - formal rules for evaluating candidate hypotheses.

This module defines the explicit evaluation policy per the Phase 3A requirements:
- Evidence considered: new evidence since hypothesis generation
- Predictions: the hypothesis's predicted_consequences
- Falsification criteria: the hypothesis's falsification_criterion
- Supporting evidence: observations matching predictions
- Contradicting evidence: observations matching falsification criterion
- Confidence: the calibrated confidence score for the hypothesis
- Decision rule: explicit logic for confirmed/falsified/insufficient
- Insufficient evidence state: when neither confirmation nor falsification is warranted

The policy is conservative: it NEVER confirms a hypothesis solely because
confidence is high. Confidence is a necessary signal, NOT a sufficient one.
"""
from dataclasses import dataclass
from typing import Any

from libs.learning.confidence import Confidence
from libs.reasoning.hypothesis import Hypothesis

# Policy constants (fixed a priori, never tuned)
MIN_PREDICTIONS_FOR_CONFIRMATION = 2
MIN_CONTRADICTIONS_FOR_FALSIFICATION = 1
CONFIDENCE_THRESHOLD_CONFIRM = 0.75
CONFIDENCE_THRESHOLD_FALSIFY = 0.30
_MAX_SUPPORTED_PREVIEW = 2


@dataclass(frozen=True)
class EvaluationInputs:
    """Inputs to the evaluation decision rule.

    All fields are derived from observed data and the hypothesis itself.
    """

    hypothesis: Hypothesis
    new_evidence_observations: list[dict[str, Any]]  # structured observations
    confidence: Confidence | None


@dataclass(frozen=True)
class EvaluationDecision:
    """Result of applying the evaluation policy.

    Includes the result, supporting counts, and a detailed rationale.
    """

    result: str  # confirmed, falsified, insufficient
    support_count: int
    contradiction_count: int
    rationale: str


# Minimum keyword length for fuzzy matching (avoids matching on short words).
_MIN_KEYWORD_LEN = 4


def _observation_matches_prediction(
    observation: dict[str, Any], prediction: str
) -> bool:
    """Check if an observation matches a predicted consequence.

    In the MVP, this is a simple text containment check. Future versions
    may use structured metric comparison.
    """
    obs_text = str(observation.get("description", "")).lower()
    pred_text = prediction.lower()
    return pred_text in obs_text or any(
        keyword in obs_text
        for keyword in pred_text.split()
        if len(keyword) > _MIN_KEYWORD_LEN
    )


def _observation_matches_falsification(
    observation: dict[str, Any], falsification_criterion: str
) -> bool:
    """Check if an observation matches the falsification criterion.

    The falsification criterion is a concrete outcome that would demonstrate
    the hypothesis false.
    """
    obs_text = str(observation.get("description", "")).lower()
    fals_text = falsification_criterion.lower()
    return fals_text in obs_text or any(
        keyword in obs_text
        for keyword in fals_text.split()
        if len(keyword) > _MIN_KEYWORD_LEN
    )


def evaluate_evidence_against_hypothesis(
    hypothesis: Hypothesis, observations: list[dict[str, Any]]
) -> tuple[int, int, list[str], list[str]]:
    """Evaluate a set of observations against a hypothesis's predictions.

    Returns:
        support_count: number of predictions satisfied
        contradiction_count: number of falsification criteria met
        supported_predictions: list of predictions that were supported
        contradicted_predictions: list of falsification criteria that were met
    """
    support_count = 0
    contradiction_count = 0
    supported: list[str] = []
    contradicted: list[str] = []

    for prediction in hypothesis.predicted_consequences:
        matched = any(
            _observation_matches_prediction(obs, prediction) for obs in observations
        )
        if matched:
            support_count += 1
            supported.append(prediction)

    # Check falsification criterion
    for obs in observations:
        if _observation_matches_falsification(obs, hypothesis.falsification_criterion):
            contradiction_count += 1
            contradicted.append(hypothesis.falsification_criterion)
            break  # One match is enough for falsification

    return support_count, contradiction_count, supported, contradicted


def apply_evaluation_policy(inputs: EvaluationInputs) -> EvaluationDecision:
    """Apply the formal evaluation policy to decide a hypothesis's status.

    Decision Rule (conservative, evidence-based):

    1. FALSIFIED if:
       - At least MIN_CONTRADICTIONS_FOR_FALSIFICATION falsification criterion is met
       - AND confidence_score < CONFIDENCE_THRESHOLD_FALSIFY
         (low confidence reinforces falsification)
       - Rationale: Evidence directly contradicts the hypothesis's core prediction.

    2. CONFIRMED if:
       - At least MIN_PREDICTIONS_FOR_CONFIRMATION predictions are supported
       - AND confidence_score >= CONFIDENCE_THRESHOLD_CONFIRM
       - AND no falsification criterion is met
       - Rationale: Multiple independent predictions confirmed with calibrated confidence.

    3. INSUFFICIENT otherwise:
       - Evidence does not meet thresholds for confirmation or falsification
       - Hypothesis remains candidate
       - Rationale: Explicit statement of what is missing.

    The policy is CONSERVATIVE:
    - Confidence alone never confirms (necessary but not sufficient)
    - Single prediction match never confirms (requires multiple)
    - Falsification requires explicit contradiction + low confidence
    - Ambiguity always defaults to INSUFFICIENT (keeps candidate)
    """
    hypothesis = inputs.hypothesis
    observations = inputs.new_evidence_observations
    confidence = inputs.confidence

    confidence_score = confidence.confidence_score if confidence else 0.0

    # Evaluate evidence
    support_count, contradiction_count, supported, contradicted = (
        evaluate_evidence_against_hypothesis(hypothesis, observations)
    )

    # Rule 1: Falsification
    if contradiction_count >= MIN_CONTRADICTIONS_FOR_FALSIFICATION:
        if confidence_score < CONFIDENCE_THRESHOLD_FALSIFY:
            return EvaluationDecision(
                result="falsified",
                support_count=support_count,
                contradiction_count=contradiction_count,
                rationale=(
                    f"Falsification criterion met ({contradiction_count} contradiction(s)). "
                    f"Confidence is low ({confidence_score:.2f} < {CONFIDENCE_THRESHOLD_FALSIFY}). "
                    f"Contradicted: {contradicted[0] if contradicted else 'N/A'}"
                ),
            )
        # Falsification criterion met but confidence is high - keep as insufficient
        # (conservative: don't falsify when confidence suggests hypothesis may still hold)
        return EvaluationDecision(
            result="insufficient",
            support_count=support_count,
            contradiction_count=contradiction_count,
            rationale=(
                f"Falsification criterion met but confidence is high "
                f"({confidence_score:.2f} >= {CONFIDENCE_THRESHOLD_FALSIFY}). "
                f"Requires more evidence to resolve ambiguity."
            ),
        )

    # Rule 2: Confirmation
    if support_count >= MIN_PREDICTIONS_FOR_CONFIRMATION:
        if confidence_score >= CONFIDENCE_THRESHOLD_CONFIRM:
            supported_preview = (
                f"Supported: {', '.join(supported[:_MAX_SUPPORTED_PREVIEW])}"
                f"{'...' if len(supported) > _MAX_SUPPORTED_PREVIEW else ''}"
            )
            return EvaluationDecision(
                result="confirmed",
                support_count=support_count,
                contradiction_count=contradiction_count,
                rationale=(
                    f"{support_count} prediction(s) supported with high confidence "
                    f"({confidence_score:.2f} >= {CONFIDENCE_THRESHOLD_CONFIRM}). "
                    f"No falsification criterion met. "
                    f"{supported_preview}"
                ),
            )
        # Multiple predictions supported but confidence too low - keep as insufficient
        return EvaluationDecision(
            result="insufficient",
            support_count=support_count,
            contradiction_count=contradiction_count,
            rationale=(
                f"{support_count} prediction(s) supported but confidence is low "
                f"({confidence_score:.2f} < {CONFIDENCE_THRESHOLD_CONFIRM}). "
                f"Requires higher calibrated confidence for confirmation."
            ),
        )

    # Rule 3: Insufficient evidence (default)
    return EvaluationDecision(
        result="insufficient",
        support_count=support_count,
        contradiction_count=contradiction_count,
        rationale=(
            f"Insufficient evidence for confirmation or falsification. "
            f"Support: {support_count}/{MIN_PREDICTIONS_FOR_CONFIRMATION} predictions, "
            f"Contradictions: {contradiction_count}, "
            f"Confidence: {confidence_score:.2f}. "
            f"Hypothesis remains candidate."
        ),
    )


def get_latest_confidence_for_hypothesis(
    confidence_store: Any, tenant_id: Any, hypothesis_id: Any
) -> Confidence | None:
    """Get the most recent confidence calibration for a hypothesis.

    Pure function - the caller must provide the store.
    """
    # This will be implemented by the service using the ConfidenceStore
    return None