"""Hypothesis Evaluation Policy - formal rules (Reasoning / Evaluate).

Canonical input: **Evidence** (the Perception output). The Evaluate capability
never reads raw Observations; it consumes the structured knowledge produced by
Perception (Observation -> Evidence -> Context). Reading the observation bus
directly would violate the Cognitive Boundary (cognitive-architecture.md R3/R7:
Reasoning acts on knowledge, never directly on the world). See AGENTS.md and the
Framework lexicon: Evidence is the first organization of observations that makes
reasoning possible.

Matching: the Evidence -> Hypothesis matcher is an **explicit, reliability-tagged**
component. In the MVP the matcher is a deterministic textual matcher over the
Evidence description (`reliability="heuristic"`). Textual matching is NOT a
reliable evaluator (it can produce false positives), so when the evidence basis
is heuristic the policy refuses to auto-promote a candidate Hypothesis into a
terminal state: it records the counts, but downgrades `confirmed`/`falsified` to
`insufficient` (the Hypothesis stays candidate). A reliable/structured evidence
basis (future phase) lifts that gate.

Formal decision rule (Confidence is gating/calibration, never a substitute for
Evidence - cognitive-lexicon/confidence.md):

- FALSIFIED if the falsification criterion is met by evidence. Confidence does
  NOT block falsification: a met falsification criterion means observed evidence
  contradicts the hypothesis; Confidence is a metacognitive calibration of the
  system's reliability, not a property of reality, so high Confidence cannot make
  contradictory evidence disappear.
- CONFIRMED if enough predictions are corroborated AND Confidence meets the
  calibration threshold AND no falsification criterion is met. Evidence
  corroboration is the primary driver; Confidence is necessary-but-not-sufficient
  gating (it calibrates the strength of the conclusion, it does not create one).
- INSUFFICIENT otherwise (Hypothesis remains candidate; never silently confirmed
  or falsified).
"""
from dataclasses import dataclass

from libs.learning.confidence import Confidence
from libs.perception.evidence import Evidence
from libs.reasoning.hypothesis import Hypothesis

# Policy constants (fixed a priori, never tuned).
MIN_PREDICTIONS_FOR_CONFIRMATION = 2
MIN_CONTRADICTIONS_FOR_FALSIFICATION = 1
CONFIDENCE_THRESHOLD_CONFIRM = 0.75
# Documented for transparency. Confidence is NOT used to block falsification
# (a met falsification criterion is evidence-based regardless of confidence), so
# this threshold is retained as a published constant but is no longer a gate.
CONFIDENCE_THRESHOLD_FALSIFY = 0.30
_MAX_SUPPORTED_PREVIEW = 2
# Reliability label for the MVP matcher (textual over Evidence descriptions).
MATCHER_RELIABILITY = "heuristic"

# Minimum keyword length for textual matching (avoids matching on short words).
_MIN_KEYWORD_LEN = 4


@dataclass(frozen=True)
class EvaluationInputs:
    """Inputs to the evaluation decision rule.

    All fields are derived from observed data and the hypothesis itself. The
    canonical evidence basis is the list of Evidence artifacts produced by
    Perception; the Evaluation never reaches into the Observation store.
    """

    hypothesis: Hypothesis
    evidence: list[Evidence]  # canonical Perception artifact
    confidence: Confidence | None
    evidence_basis_reliable: bool = False  # gate for terminal-state promotion


@dataclass(frozen=True)
class EvaluationDecision:
    """Result of applying the evaluation policy.

    Includes the result, supporting counts, and a detailed rationale.
    """

    result: str  # confirmed, falsified, insufficient
    support_count: int
    contradiction_count: int
    rationale: str


@dataclass(frozen=True)
class _MatchResult:
    """Counts and matched items from comparing Evidence against a Hypothesis."""

    support_count: int
    contradiction_count: int
    supported: list[str]
    contradicted: list[str]


def _evidence_supports_prediction(evidence: Evidence, prediction: str) -> bool:
    """Heuristic check: does Evidence corroborate a predicted consequence?

    MVP textual matcher over the Evidence description / organization type.
    Explicitly labelled heuristic (MATCHER_RELIABILITY) and never used as the
    sole basis for terminal-state promotion.
    """
    text = " ".join([evidence.description, evidence.organization_type]).lower()
    pred = prediction.lower()
    return pred in text or any(
        kw in text for kw in pred.split() if len(kw) > _MIN_KEYWORD_LEN
    )


def _evidence_meets_falsification(evidence: Evidence, criterion: str) -> bool:
    """Heuristic check: does Evidence meet the falsification criterion?

    MVP textual matcher over the Evidence description / organization type.
    """
    text = " ".join([evidence.description, evidence.organization_type]).lower()
    crit = criterion.lower()
    return crit in text or any(
        kw in text for kw in crit.split() if len(kw) > _MIN_KEYWORD_LEN
    )


def evaluate_evidence_against_hypothesis(
    hypothesis: Hypothesis, evidence: list[Evidence]
) -> tuple[int, int, list[str], list[str]]:
    """Evaluate a set of Evidence artifacts against a hypothesis's predictions.

    Returns:
        support_count: number of predictions corroborated by evidence
        contradiction_count: number of falsification criteria met
        supported_predictions: predictions that were supported
        contradicted_criteria: falsification criteria that were met
    """
    support_count = 0
    contradiction_count = 0
    supported: list[str] = []
    contradicted: list[str] = []

    for prediction in hypothesis.predicted_consequences:
        matched = any(
            _evidence_supports_prediction(ev, prediction) for ev in evidence
        )
        if matched:
            support_count += 1
            supported.append(prediction)

    # Check falsification criterion (one match is sufficient).
    for ev in evidence:
        if _evidence_meets_falsification(ev, hypothesis.falsification_criterion):
            contradiction_count += 1
            contradicted.append(hypothesis.falsification_criterion)
            break

    return support_count, contradiction_count, supported, contradicted


def _formal_decision(
    match: _MatchResult,
    confidence_score: float,
    reliable: bool,
) -> tuple[str, str]:
    """Apply the formal evaluation rule (see module docstring).

    Returns (result, rationale). When the evidence basis is heuristic, terminal
    results (confirmed/falsified) are downgraded to `insufficient` so the
    service never auto-promotes a Hypothesis on an unreliable signal.
    """
    # Rule 1: Falsification is evidence-based.
    if match.contradiction_count >= MIN_CONTRADICTIONS_FOR_FALSIFICATION:
        if reliable:
            rationale = (
                f"Falsification criterion met ({match.contradiction_count} contradiction(s)). "
                f"Observed evidence contradicts the hypothesis; Confidence does not "
                f"override contradictory evidence. "
                f"Contradicted: {match.contradicted[0] if match.contradicted else 'N/A'}"
            )
            return "falsified", rationale
        rationale = (
            f"Falsification criterion met by heuristic evidence "
            f"({match.contradiction_count} contradiction(s)); terminal promotion requires a "
            f"reliable/structured evidence basis (see evaluation_policy). Hypothesis "
            f"remains candidate pending explicit evaluation."
        )
        return "insufficient", rationale

    # Rule 2: Confirmation requires corroboration AND calibrated confidence.
    if match.support_count >= MIN_PREDICTIONS_FOR_CONFIRMATION:
        if confidence_score >= CONFIDENCE_THRESHOLD_CONFIRM:
            if reliable:
                supported_preview = (
                    f"Supported: {', '.join(match.supported[:_MAX_SUPPORTED_PREVIEW])}"
                    f"{'...' if len(match.supported) > _MAX_SUPPORTED_PREVIEW else ''}"
                )
                rationale = (
                    f"{match.support_count} prediction(s) corroborated with high confidence "
                    f"({confidence_score:.2f} >= {CONFIDENCE_THRESHOLD_CONFIRM}). "
                    f"No falsification criterion met. {supported_preview}"
                )
                return "confirmed", rationale
            rationale = (
                f"{match.support_count} prediction(s) corroborated with high confidence "
                f"({confidence_score:.2f} >= {CONFIDENCE_THRESHOLD_CONFIRM}) on heuristic "
                f"evidence; terminal promotion requires a reliable/structured evidence "
                f"basis. Hypothesis remains candidate."
            )
            return "insufficient", rationale
        rationale = (
            f"{match.support_count} prediction(s) corroborated but Confidence is low "
            f"({confidence_score:.2f} < {CONFIDENCE_THRESHOLD_CONFIRM}). "
            f"Confidence is necessary-but-not-sufficient gating; requires higher "
            f"calibrated confidence for confirmation."
        )
        return "insufficient", rationale

    # Rule 3: Insufficient evidence (default - candidate preserved).
    rationale = (
        f"Insufficient evidence for confirmation or falsification. "
        f"Support: {match.support_count}/{MIN_PREDICTIONS_FOR_CONFIRMATION} predictions, "
        f"Contradictions: {match.contradiction_count}, "
        f"Confidence: {confidence_score:.2f}. "
        f"Hypothesis remains candidate."
    )
    return "insufficient", rationale


def apply_evaluation_policy(inputs: EvaluationInputs) -> EvaluationDecision:
    """Apply the formal evaluation policy to decide a hypothesis's status.

    The decision is conservative and evidence-first:
    - Confidence alone never confirms (necessary but not sufficient).
    - A met falsification criterion falsifies regardless of Confidence.
    - Ambiguity and heuristic-only signal always default to INSUFFICIENT.
    """
    confidence = inputs.confidence
    confidence_score = confidence.confidence_score if confidence else 0.0

    support_count, contradiction_count, supported, contradicted = (
        evaluate_evidence_against_hypothesis(inputs.hypothesis, inputs.evidence)
    )
    match = _MatchResult(
        support_count=support_count,
        contradiction_count=contradiction_count,
        supported=supported,
        contradicted=contradicted,
    )

    result, rationale = _formal_decision(
        match=match,
        confidence_score=confidence_score,
        reliable=inputs.evidence_basis_reliable,
    )

    return EvaluationDecision(
        result=result,
        support_count=support_count,
        contradiction_count=contradiction_count,
        rationale=rationale,
    )
