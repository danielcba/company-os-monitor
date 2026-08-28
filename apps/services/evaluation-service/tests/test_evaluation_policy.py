"""Unit tests for the Hypothesis Evaluation Policy.

The canonical evaluation input is Evidence (Perception output), never raw
Observations. These tests pin the formal decision rules:

A. candidate + no evidence -> insufficient (candidate preserved)
B. candidate + insufficient evidence -> insufficient
C. candidate + sufficient corroboration (reliable basis) -> confirmed
D. candidate + valid falsification (reliable basis) -> falsified
   (high Confidence does NOT block falsification - it is evidence-based)
E. mixed evidence -> deterministic outcome
F. deterministic evaluation (same inputs -> same output)
G. provenance of evaluation (rationale includes reasoning + confidence)
H. high confidence without sufficient evidence -> NOT confirmed
I. heuristic evidence basis is never auto-promoted to a terminal state
"""
import uuid
from datetime import UTC, datetime

from libs.learning.confidence import Confidence, ConfidenceCreate, build_confidence
from libs.perception.evidence import Evidence
from libs.perception.observation import QualityClass
from libs.reasoning.evaluation_policy import (
    CONFIDENCE_THRESHOLD_CONFIRM,
    CONFIDENCE_THRESHOLD_FALSIFY,
    MATCHER_RELIABILITY,
    MIN_CONTRADICTIONS_FOR_FALSIFICATION,
    MIN_PREDICTIONS_FOR_CONFIRMATION,
    EvaluationInputs,
    apply_evaluation_policy,
    evaluate_evidence_against_hypothesis,
)
from libs.reasoning.hypothesis import STATUS_CANDIDATE, Hypothesis


def make_hypothesis(
    *,
    description: str = "Test hypothesis",
    predicted_consequences: list[str] | None = None,
    falsification_criterion: str = "If X does not happen, hypothesis is false",
    status: str = STATUS_CANDIDATE,
) -> Hypothesis:
    """Create a test hypothesis."""
    return Hypothesis(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        anomaly_ids=[uuid.uuid4()],
        pattern_ids=[uuid.uuid4()],
        description=description,
        predicted_consequences=predicted_consequences or ["Prediction A", "Prediction B"],
        falsification_criterion=falsification_criterion,
        coherence_score=0.5,
        status=status,
        generated_at=datetime.now(UTC),
    )


def make_confidence(score: float, target_id: uuid.UUID | None = None) -> Confidence:
    """Create a test confidence."""
    create = ConfidenceCreate(
        tenant_id=uuid.uuid4(),
        target_type="hypothesis",
        target_id=target_id or uuid.uuid4(),
        evidential_support=0.8,
        explanatory_coherence=0.7,
        historical_calibration=1.0,
        confidence_score=score,
        alpha=0.5,
        calibration_justification="Test",
        calibration_error_estimate=0.0,
        evidence_ids=[],
    )
    return build_confidence(create)


def make_evidence(descriptions: list[str], organization_type: str = "test_org") -> list[Evidence]:
    """Create Evidence artifacts for testing (canonical Perception output)."""
    return [
        Evidence(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            observation_ids=[uuid.uuid4()],
            organization_type=organization_type,
            description=desc,
            quality_class=QualityClass.Q1,
            weight=1.0,
            organized_at=datetime.now(UTC),
        )
        for desc in descriptions
    ]


class TestEvaluateEvidenceAgainstHypothesis:
    """Tests for the evidence evaluation logic (now Evidence-based)."""

    def test_supports_predictions(self):
        hypothesis = make_hypothesis(
            predicted_consequences=["disk usage increases", "log volume grows"]
        )
        evidence = make_evidence([
            "disk usage increases significantly",
            "log volume grows rapidly",
        ])
        support, contradiction, supported, contradicted = (
            evaluate_evidence_against_hypothesis(hypothesis, evidence)
        )
        assert support == 2
        assert contradiction == 0
        assert len(supported) == 2

    def test_contradicts_falsification_criterion(self):
        hypothesis = make_hypothesis(
            falsification_criterion="disk usage remains stable"
        )
        evidence = make_evidence(["disk usage remains stable"])
        support, contradiction, supported, contradicted = (
            evaluate_evidence_against_hypothesis(hypothesis, evidence)
        )
        assert contradiction == 1
        assert len(contradicted) == 1

    def test_no_match_returns_zero(self):
        hypothesis = make_hypothesis(
            predicted_consequences=["disk capacity increases significantly"],
            falsification_criterion="disk capacity remains flat",
        )
        evidence = make_evidence([
            "cpu temperature rises unexpectedly high",
            "memory consumption drops sharply down",
        ])
        support, contradiction, supported, contradicted = (
            evaluate_evidence_against_hypothesis(hypothesis, evidence)
        )
        assert contradiction == 0

    def test_mixed_evidence(self):
        hypothesis = make_hypothesis(
            predicted_consequences=["disk usage increases", "log volume grows"],
            falsification_criterion="disk usage remains stable",
        )
        evidence = make_evidence([
            "disk usage increases significantly",
            "disk usage remains stable",
        ])
        support, contradiction, supported, contradicted = (
            evaluate_evidence_against_hypothesis(hypothesis, evidence)
        )
        assert support == 1
        assert contradiction == 1


class TestApplyEvaluationPolicy:
    """Tests for the formal evaluation decision rules."""

    def test_insufficient_evidence_keeps_candidate(self):
        """A. candidate with insufficient evidence -> insufficient (stays candidate)."""
        hypothesis = make_hypothesis(predicted_consequences=["Prediction A", "Prediction B"])
        evidence = make_evidence([])
        confidence = make_confidence(0.8, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "insufficient"
        assert decision.support_count == 0
        assert "Insufficient evidence" in decision.rationale

    def test_single_prediction_not_enough_for_confirmation(self):
        """B. Single prediction match with high confidence -> insufficient (needs multiple)."""
        hypothesis = make_hypothesis(predicted_consequences=["Disk usage increases", "Log volume grows"])
        evidence = make_evidence(["Disk usage increases confirmed"])
        confidence = make_confidence(0.9, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "insufficient"
        assert decision.support_count == 1
        assert "Insufficient evidence" in decision.rationale

    def test_multiple_predictions_high_confidence_confirms(self):
        """C. Multiple corroborated predictions with high confidence (reliable) -> confirmed."""
        hypothesis = make_hypothesis(predicted_consequences=["Prediction A", "Prediction B"])
        evidence = make_evidence(["Prediction A confirmed", "Prediction B confirmed"])
        confidence = make_confidence(0.85, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "confirmed"
        assert decision.support_count >= MIN_PREDICTIONS_FOR_CONFIRMATION

    def test_falsification_criterion_met_low_confidence_falsifies(self):
        """D. Falsification criterion met with low confidence -> falsified (reliable)."""
        hypothesis = make_hypothesis(
            predicted_consequences=["Prediction A", "Prediction B"],
            falsification_criterion="disk usage remains stable",
        )
        evidence = make_evidence(["disk usage remains stable"])
        confidence = make_confidence(0.2, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "falsified"
        assert decision.contradiction_count >= MIN_CONTRADICTIONS_FOR_FALSIFICATION

    def test_falsification_criterion_met_high_confidence_still_falsifies(self):
        """D. Falsification criterion met with HIGH confidence -> still falsified.

        Confidence is a metacognitive calibration, NOT a substitute for
        contradictory evidence (Blocker #4). High confidence must not override a
        met falsification criterion.
        """
        hypothesis = make_hypothesis(
            predicted_consequences=["Prediction A", "Prediction B"],
            falsification_criterion="disk usage remains stable",
        )
        evidence = make_evidence(["disk usage remains stable"])
        confidence = make_confidence(0.99, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "falsified"
        assert "Confidence does not" in decision.rationale or "contradict" in decision.rationale

    def test_contradictory_insufficient_evidence_insufficient(self):
        """D. Contradictory but insufficient evidence -> insufficient."""
        hypothesis = make_hypothesis(
            predicted_consequences=["Prediction A", "Prediction B", "Prediction C"],
            falsification_criterion="disk usage remains stable",
        )
        evidence = make_evidence(["Prediction A confirmed", "Some unrelated observation"])
        confidence = make_confidence(0.6, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "insufficient"

    def test_no_confidence_defaults_to_low(self):
        hypothesis = make_hypothesis(predicted_consequences=["Prediction A", "Prediction B"])
        evidence = make_evidence(["Prediction A confirmed", "Prediction B confirmed"])
        inputs = EvaluationInputs(hypothesis, evidence, None, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "insufficient"
        assert "confidence is low" in decision.rationale.lower() or "low" in decision.rationale.lower()

    def test_deterministic_evaluation(self):
        """F. Same inputs always produce same output."""
        hypothesis = make_hypothesis()
        evidence = make_evidence(["Prediction A confirmed", "Prediction B confirmed"])
        confidence = make_confidence(0.85, hypothesis.id)
        inputs1 = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        inputs2 = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision1 = apply_evaluation_policy(inputs1)
        decision2 = apply_evaluation_policy(inputs2)
        assert decision1.result == decision2.result
        assert decision1.support_count == decision2.support_count
        assert decision1.contradiction_count == decision2.contradiction_count
        assert decision1.rationale == decision2.rationale

    def test_provenance_in_rationale(self):
        """G. Rationale includes explicit reasoning + confidence."""
        hypothesis = make_hypothesis(predicted_consequences=["Prediction A", "Prediction B"])
        evidence = make_evidence(["Prediction A confirmed", "Prediction B confirmed"])
        confidence = make_confidence(0.85, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert "prediction" in decision.rationale.lower()
        assert str(confidence.confidence_score)[:4] in decision.rationale

    def test_heuristic_basis_never_promotes(self):
        """I. Heuristic evidence basis is never auto-promoted to a terminal state."""
        # Even with falsification met + low confidence, on a heuristic basis the
        # service must NOT falsify (it records insufficient + candidate preserved).
        hypothesis = make_hypothesis(
            predicted_consequences=["Prediction A", "Prediction B"],
            falsification_criterion="disk usage remains stable",
        )
        evidence = make_evidence(["disk usage remains stable"])
        confidence = make_confidence(0.2, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=False)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "insufficient"
        assert "reliable" in decision.rationale.lower()

        # And confirmation on heuristic basis is also downgraded.
        hypothesis2 = make_hypothesis(predicted_consequences=["Prediction A", "Prediction B"])
        evidence2 = make_evidence(["Prediction A confirmed", "Prediction B confirmed"])
        confidence2 = make_confidence(0.9, hypothesis2.id)
        inputs2 = EvaluationInputs(hypothesis2, evidence2, confidence2, evidence_basis_reliable=False)
        decision2 = apply_evaluation_policy(inputs2)
        assert decision2.result == "insufficient"
        assert "reliable" in decision2.rationale.lower()


class TestEvaluationPolicyConstants:
    """Tests that policy constants are properly defined."""

    def test_min_predictions_for_confirmation(self):
        assert MIN_PREDICTIONS_FOR_CONFIRMATION == 2

    def test_min_contradictions_for_falsification(self):
        assert MIN_CONTRADICTIONS_FOR_FALSIFICATION == 1

    def test_confidence_thresholds(self):
        assert CONFIDENCE_THRESHOLD_CONFIRM == 0.75
        assert CONFIDENCE_THRESHOLD_FALSIFY == 0.30

    def test_matcher_reliability_is_heuristic_mvp(self):
        assert MATCHER_RELIABILITY == "heuristic"


class TestConservativePolicy:
    """Tests that the policy is conservative (never confirms on confidence alone)."""

    def test_high_confidence_alone_never_confirms(self):
        hypothesis = make_hypothesis(predicted_consequences=["Prediction A", "Prediction B"])
        evidence = make_evidence([])
        confidence = make_confidence(0.99, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "insufficient"
        assert "Insufficient evidence" in decision.rationale

    def test_single_prediction_never_confirms(self):
        hypothesis = make_hypothesis(predicted_consequences=["Prediction A"])
        evidence = make_evidence(["Prediction A confirmed"])
        confidence = make_confidence(0.99, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "insufficient"

    def test_ambiguity_defaults_to_insufficient(self):
        hypothesis = make_hypothesis(
            predicted_consequences=["Prediction A", "Prediction B"],
            falsification_criterion="Falsification X",
        )
        # Neutral evidence that does not substring-match either prediction or the
        # falsification criterion: ambiguity must default to insufficient.
        evidence = make_evidence(["Observation alpha noted", "Observation beta noted"])
        confidence = make_confidence(0.5, hypothesis.id)
        inputs = EvaluationInputs(hypothesis, evidence, confidence, evidence_basis_reliable=True)
        decision = apply_evaluation_policy(inputs)
        assert decision.result == "insufficient"
