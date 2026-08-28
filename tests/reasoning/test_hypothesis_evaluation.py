"""Unit tests for Hypothesis Evaluation (P7 learning loop).

Tests the evaluation logic per audit requirements:
A. candidate + insufficient evidence -> candidate
B. candidate + corroborating evidence -> confirmed
C. candidate + falsifying evidence -> falsified
D. contradictory but insufficient -> candidate
E. re-evaluation -> no destruction of historical evaluation
F. tenant isolation
G. provenance
H. idempotency
"""
import uuid
from datetime import datetime

import pytest

from libs.reasoning.hypothesis import (
    STATUS_CANDIDATE,
    STATUS_CONFIRMED,
    STATUS_FALSIFIED,
    Hypothesis,
    HypothesisCreate,
    build_hypothesis,
    evaluate_hypothesis,
)

TENANT = uuid.UUID("00000000-0000-0000-0000-00000000000a")


def _make_hypothesis(
    *,
    tenant_id: uuid.UUID = TENANT,
    anomaly_ids: list[uuid.UUID] | None = None,
    pattern_ids: list[uuid.UUID] | None = None,
    description: str = "Test hypothesis",
    predicted_consequences: list[str] | None = None,
    falsification_criterion: str = "Falsification criterion not met",
    coherence_score: float = 0.7,
    status: str = STATUS_CANDIDATE,
) -> Hypothesis:
    create = HypothesisCreate(
        tenant_id=tenant_id,
        anomaly_ids=anomaly_ids or [uuid.uuid4()],
        pattern_ids=pattern_ids or [],
        description=description,
        predicted_consequences=predicted_consequences or ["Prediction 1", "Prediction 2"],
        falsification_criterion=falsification_criterion,
        coherence_score=coherence_score,
        status=status,
    )
    return build_hypothesis(create)


def test_evaluation_insufficient_evidence_remains_candidate():
    """A. candidate + insufficient evidence -> candidate."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Revenue increases", "Cost decreases"],
        falsification_criterion="Revenue decreases",
    )
    # No evidence provided
    result = evaluate_hypothesis(hypothesis)
    assert result.new_status == STATUS_CANDIDATE
    assert result.prior_status == STATUS_CANDIDATE
    assert not result.evidence_sufficient
    assert result.predicted_consequences_corroborated == 0


def test_evaluation_no_matching_evidence_remains_candidate():
    """A. candidate + irrelevant evidence -> candidate (insufficient)."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Revenue increases", "Cost decreases"],
        falsification_criterion="Revenue decreases",
    )
    # Evidence that doesn't match predictions or falsification
    result = evaluate_hypothesis(
        hypothesis,
        supporting_evidence=[{"metric": "unrelated", "value": "something"}],
        contradicting_evidence=[{"metric": "also_unrelated", "value": "else"}],
    )
    assert result.new_status == STATUS_CANDIDATE
    assert not result.evidence_sufficient


def test_evaluation_corroborating_evidence_confirmed():
    """B. candidate + sufficient corroborating evidence -> confirmed."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Revenue increases", "Cost decreases"],
        falsification_criterion="Revenue decreases",
    )
    # Evidence matching both predictions
    supporting = [
        {"metric": "revenue", "value": "Revenue increases by 10%"},
        {"metric": "cost", "value": "Cost decreases by 5%"},
    ]
    result = evaluate_hypothesis(hypothesis, supporting_evidence=supporting)
    assert result.new_status == STATUS_CONFIRMED
    assert result.evidence_sufficient
    assert result.predicted_consequences_corroborated == 2
    assert result.predicted_consequences_total == 2


def test_evaluation_majority_corroboration_confirmed():
    """B. candidate + majority corroboration -> confirmed."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Pred A", "Pred B", "Pred C"],
        falsification_criterion="Falsification",
    )
    # Evidence matching 2 of 3 predictions (majority)
    supporting = [
        {"metric": "a", "value": "Pred A observed"},
        {"metric": "b", "value": "Pred B observed"},
    ]
    result = evaluate_hypothesis(hypothesis, supporting_evidence=supporting)
    assert result.new_status == STATUS_CONFIRMED
    assert result.predicted_consequences_corroborated == 2
    assert result.predicted_consequences_total == 3


def test_evaluation_partial_corroboration_not_majority_remains_candidate():
    """D. contradictory but insufficient -> candidate (partial corroboration < majority)."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Pred A", "Pred B", "Pred C", "Pred D"],
        falsification_criterion="Falsification",
    )
    # Evidence matching only 1 of 4 predictions (not majority)
    supporting = [{"metric": "a", "value": "Pred A observed"}]
    result = evaluate_hypothesis(hypothesis, supporting_evidence=supporting)
    assert result.new_status == STATUS_CANDIDATE
    assert result.predicted_consequences_corroborated == 1
    assert result.predicted_consequences_total == 4
    assert "Partial corroboration" in result.evaluation_rationale


def test_evaluation_falsification_criterion_met_falsified():
    """C. candidate + falsifying evidence -> falsified."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Revenue increases"],
        falsification_criterion="Revenue decreases",
    )
    # Evidence matching falsification criterion
    contradicting = [{"metric": "revenue", "value": "Revenue decreases by 5%"}]
    result = evaluate_hypothesis(hypothesis, contradicting_evidence=contradicting)
    assert result.new_status == STATUS_FALSIFIED
    assert result.falsification_criterion_met
    assert "Falsification criterion met" in result.evaluation_rationale


def test_evaluation_falsification_takes_priority_over_corroboration():
    """C. falsification criterion met -> falsified even with some corroboration."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Pred A", "Pred B"],
        falsification_criterion="Critical failure",
    )
    supporting = [{"metric": "a", "value": "Pred A observed"}]
    contradicting = [{"metric": "critical", "value": "Critical failure detected"}]
    result = evaluate_hypothesis(
        hypothesis, supporting_evidence=supporting, contradicting_evidence=contradicting
    )
    assert result.new_status == STATUS_FALSIFIED
    assert result.falsification_criterion_met


def test_evaluation_confirmed_hypothesis_not_reevaluated():
    """E. re-evaluation of confirmed -> no status change (append-only, P1)."""
    hypothesis = _make_hypothesis(status=STATUS_CONFIRMED)
    # Even with falsifying evidence, confirmed stays confirmed
    contradicting = [{"metric": "x", "value": "Falsification criterion met"}]
    result = evaluate_hypothesis(hypothesis, contradicting_evidence=contradicting)
    assert result.new_status == STATUS_CONFIRMED
    assert result.prior_status == STATUS_CONFIRMED
    assert "already confirmed" in result.evaluation_rationale.lower()


def test_evaluation_falsified_hypothesis_not_reevaluated():
    """E. re-evaluation of falsified -> no status change (append-only, P1)."""
    hypothesis = _make_hypothesis(status=STATUS_FALSIFIED)
    # Even with corroborating evidence, falsified stays falsified
    supporting = [{"metric": "x", "value": "All predictions corroborated"}]
    result = evaluate_hypothesis(hypothesis, supporting_evidence=supporting)
    assert result.new_status == STATUS_FALSIFIED
    assert result.prior_status == STATUS_FALSIFIED
    assert "already falsified" in result.evaluation_rationale.lower()


def test_evaluation_confidence_not_sole_criterion():
    """Confidence is NOT the sole criterion for confirmation."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Pred A", "Pred B"],
        falsification_criterion="Falsification",
        coherence_score=0.9,  # High confidence
    )
    # High confidence but NO evidence -> remains candidate
    result = evaluate_hypothesis(hypothesis, confidence_score=0.95)
    assert result.new_status == STATUS_CANDIDATE
    assert not result.evidence_sufficient
    assert result.confidence_score == 0.95


def test_evaluation_confidence_supports_but_not_decides():
    """Confidence supports evaluation but doesn't decide alone."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Pred A"],
        falsification_criterion="Falsification",
    )
    # Low confidence with corroborating evidence -> still confirmed (evidence decides)
    supporting = [{"metric": "a", "value": "Pred A observed"}]
    result = evaluate_hypothesis(hypothesis, supporting_evidence=supporting, confidence_score=0.3)
    assert result.new_status == STATUS_CONFIRMED
    assert result.confidence_score == 0.3


def test_evaluation_provenance_includes_hypothesis_id():
    """G. EvaluationResult includes hypothesis_id for provenance."""
    hypothesis = _make_hypothesis()
    result = evaluate_hypothesis(hypothesis)
    assert result.hypothesis_id == hypothesis.id
    assert isinstance(result.hypothesis_id, uuid.UUID)


def test_evaluation_provenance_includes_evidence_counts():
    """G. EvaluationResult includes evidence counts for provenance."""
    hypothesis = _make_hypothesis()
    supporting = [{"e": 1}, {"e": 2}]
    contradicting = [{"e": 3}]
    result = evaluate_hypothesis(
        hypothesis, supporting_evidence=supporting, contradicting_evidence=contradicting
    )
    assert result.supporting_evidence_count == 2
    assert result.contradicting_evidence_count == 1


def test_evaluation_provenance_includes_confidence():
    """G. EvaluationResult includes confidence_score for provenance."""
    hypothesis = _make_hypothesis()
    result = evaluate_hypothesis(hypothesis, confidence_score=0.85)
    assert result.confidence_score == 0.85


def test_evaluation_deterministic():
    """H. Same inputs -> same evaluation result (deterministic)."""
    hypothesis = _make_hypothesis()
    supporting = [{"metric": "a", "value": "Pred A observed"}]
    result1 = evaluate_hypothesis(hypothesis, supporting_evidence=supporting)
    result2 = evaluate_hypothesis(hypothesis, supporting_evidence=supporting)
    assert result1.new_status == result2.new_status
    assert result1.evaluation_rationale == result2.evaluation_rationale
    assert result1.predicted_consequences_corroborated == result2.predicted_consequences_corroborated


def test_evaluation_tenant_isolation():
    """F. Hypothesis evaluation is tenant-scoped (via hypothesis tenant_id)."""
    tenant_a = uuid.UUID("00000000-0000-0000-0000-00000000000a")
    tenant_b = uuid.UUID("00000000-0000-0000-0000-00000000000b")
    hypothesis_a = _make_hypothesis(tenant_id=tenant_a)
    hypothesis_b = _make_hypothesis(tenant_id=tenant_b)
    # Same evidence, different tenants -> different hypothesis_ids in result
    supporting = [{"metric": "a", "value": "Pred A observed"}]
    result_a = evaluate_hypothesis(hypothesis_a, supporting_evidence=supporting)
    result_b = evaluate_hypothesis(hypothesis_b, supporting_evidence=supporting)
    assert result_a.hypothesis_id != result_b.hypothesis_id
    assert result_a.hypothesis_id == hypothesis_a.id
    assert result_b.hypothesis_id == hypothesis_b.id


def test_evaluation_result_immutable():
    """EvaluationResult is frozen (P1: immutable evaluation record)."""
    hypothesis = _make_hypothesis()
    result = evaluate_hypothesis(hypothesis)
    with pytest.raises(Exception):  # pydantic ValidationError
        result.new_status = STATUS_FALSIFIED


def test_evaluation_result_contains_timestamp():
    """EvaluationResult includes evaluation_timestamp for traceability."""
    hypothesis = _make_hypothesis()
    result = evaluate_hypothesis(hypothesis)
    assert result.evaluation_timestamp is not None
    assert isinstance(result.evaluation_timestamp, datetime)


def test_evaluation_result_contains_rationale():
    """EvaluationResult includes human-readable rationale for traceability."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Pred A"],
        falsification_criterion="Falsification",
    )
    supporting = [{"metric": "a", "value": "Pred A observed"}]
    result = evaluate_hypothesis(hypothesis, supporting_evidence=supporting)
    assert result.evaluation_rationale
    assert "corroborat" in result.evaluation_rationale.lower()


def test_evaluation_single_prediction_corroborated_confirmed():
    """Single prediction corroborated -> confirmed."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Single prediction"],
        falsification_criterion="Falsification",
    )
    supporting = [{"metric": "x", "value": "Single prediction observed"}]
    result = evaluate_hypothesis(hypothesis, supporting_evidence=supporting)
    assert result.new_status == STATUS_CONFIRMED
    assert result.predicted_consequences_corroborated == 1
    assert result.predicted_consequences_total == 1


def test_evaluation_contradicting_evidence_insufficient_remains_candidate():
    """D. Contradicting evidence that doesn't meet falsification criterion -> candidate."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Pred A"],
        falsification_criterion="Specific falsification",
    )
    # Contradicting but not matching falsification criterion
    contradicting = [{"metric": "x", "value": "Some other contradiction"}]
    result = evaluate_hypothesis(hypothesis, contradicting_evidence=contradicting)
    assert result.new_status == STATUS_CANDIDATE
    assert not result.falsification_criterion_met
    assert not result.evidence_sufficient


def test_evaluation_both_supporting_and_contradicting_insufficient_remains_candidate():
    """D. Both supporting and contradicting but neither sufficient -> candidate."""
    hypothesis = _make_hypothesis(
        predicted_consequences=["Pred A", "Pred B"],
        falsification_criterion="Falsification",
    )
    supporting = [{"metric": "a", "value": "Pred A observed"}]
    contradicting = [{"metric": "x", "value": "Weak contradiction"}]
    result = evaluate_hypothesis(
        hypothesis, supporting_evidence=supporting, contradicting_evidence=contradicting
    )
    # 1 of 2 predictions corroborated = 50%, not majority
    assert result.new_status == STATUS_CANDIDATE
    assert result.predicted_consequences_corroborated == 1
    assert result.predicted_consequences_total == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])