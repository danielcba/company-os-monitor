"""Unit tests for the Calibration Model math (Learning - Calibrate).

Verifies the functions against the formal Calibration Model of the Confidence
concept (core-concepts/confidence.md): evidential support (log-odds + sigmoid),
Brier score, ECE over M bins, final confidence C_final = [alpha*S + (1-alpha)*C]
* (1 - ECE), and the real explanatory coherence (normalized constraint
satisfaction). Known values only - no database.
"""
import pytest
from libs.cognitive_core.calibration_model import (
    QUALITY_CLASS_RANGES,
    CalibrationParams,
    brier_score,
    ece_score,
    evidential_support,
    explanatory_coherence,
    final_confidence,
    quality_class_to_weight,
)


def test_quality_class_bands_and_midpoint_weights():
    assert QUALITY_CLASS_RANGES == {
        "Q1": (0.75, 1.0),
        "Q2": (0.50, 0.75),
        "Q3": (0.25, 0.50),
        "Q4": (0.00, 0.25),
    }
    assert quality_class_to_weight("Q1") == 0.875
    assert quality_class_to_weight("Q2") == 0.625
    assert quality_class_to_weight("Q3") == 0.375
    assert quality_class_to_weight("Q4") == 0.125


def test_evidential_support_log_odds_sigmoid():
    # L = 0 + 0.875 - 0.625 = 0.25 -> S = 1/(1+e^-0.25) = 0.5622 (known value).
    S = evidential_support([0.875, 0.625], [1, -1], 0.0)
    assert S == pytest.approx(0.562177, abs=1e-5)  # 0.5621765008...
    # Single strong Q1 support: S > 0.5; single contradiction: S < 0.5.
    assert evidential_support([0.875], [1]) > 0.5
    assert evidential_support([0.875], [-1]) < 0.5
    # No evidence -> uniform prior 0.5 (L = L0 = 0).
    assert evidential_support([], [], 0.0) == 0.5
    # Non-zero L0 prior (documented base rate) shifts the support.
    assert evidential_support([0.875], [1], 1.0) > evidential_support([0.875], [1], 0.0)


def test_brier_score_known_value():
    # B = ((0.9-1)^2 + (0.8-0)^2)/2 = (0.01 + 0.64)/2 = 0.325.
    assert brier_score([0.9, 0.8], [1, 0]) == pytest.approx(0.325, abs=1e-5)
    assert brier_score([], []) == 0.0


def test_ece_score_over_m_bins():
    # Two predictions in their own bins: |acc-conf| = 0.2 each -> ECE = 0.2.
    assert ece_score([0.2, 0.8], [0, 1], M=10) == pytest.approx(0.2, abs=1e-5)
    # Overconfident: conf 0.5, acc 1.0 -> ECE = 0.5.
    assert ece_score([0.5, 0.5], [1, 1], M=10) == pytest.approx(0.5, abs=1e-5)
    # Perfectly calibrated -> ECE = 0.
    assert ece_score([0.0, 0.0], [0, 0], M=10) == 0.0
    assert ece_score([], []) == 0.0


def test_ece_score_counts_perfect_predictions_in_last_bin():
    # A prediction of exactly 1.0 belongs to the last bin [(M-1)/M, 1]; it must
    # count toward ECE instead of being silently dropped (it used to be
    # excluded by p < bin_edges[m+1] while still counting in the denominator).
    assert ece_score([1.0], [1], M=10) == 0.0
    # Mis-calibrated in the last bin: conf 1.0, acc 0.0 -> ECE = 1.0 (the old
    # code dropped p=1.0 and reported 0.0, masking the overconfidence).
    assert ece_score([1.0], [0], M=10) == pytest.approx(1.0, abs=1e-5)
    # p=1.0 mis-calibrated (contribution 0.5) + p=0.5 mis-calibrated
    # (contribution 0.25) -> ECE = 0.75.
    assert ece_score([1.0, 0.5], [0, 0], M=10) == pytest.approx(0.75, abs=1e-5)


def test_final_confidence_combines_support_coherence_and_ece():
    # C_final = [0.5*0.7 + 0.5*0.6] * (1 - 0.2) = 0.65 * 0.8 = 0.52.
    assert final_confidence(0.7, 0.6, 0.2, alpha=0.5) == pytest.approx(0.52, abs=1e-5)
    # The ECE factor always penalizes: same S/C with ECE=0 scores higher.
    assert final_confidence(0.7, 0.6, 0.0, alpha=0.5) == pytest.approx(0.65, abs=1e-5)
    # alpha mixes support and coherence.
    assert final_confidence(0.9, 0.1, 0.0, alpha=1.0) == pytest.approx(0.9, abs=1e-5)
    assert final_confidence(0.9, 0.1, 0.0, alpha=0.0) == pytest.approx(0.1, abs=1e-5)


def test_explanatory_coherence_high_when_hypothesis_explains_scope():
    hypothesis = "La hipotesis explica la evidencia."
    evidence = ["resource_exhaustion_evidence", "service_degradation_evidence"]
    constraints = {
        "explains": ["resource_exhaustion_evidence", "service_degradation_evidence"],
        "contradicts": [],
    }
    C = explanatory_coherence(hypothesis, evidence, constraints)
    assert C == 1.0
    assert 0.0 <= C <= 1.0


def test_explanatory_coherence_low_when_hypothesis_contradicts_scope():
    hypothesis = "La hipotesis contradice toda la evidencia."
    evidence = ["resource_exhaustion_evidence", "service_degradation_evidence"]
    constraints = {
        "explains": [],
        "contradicts": ["resource_exhaustion_evidence", "service_degradation_evidence"],
    }
    C = explanatory_coherence(hypothesis, evidence, constraints)
    assert C == 0.0


def test_explanatory_coherence_partial_explanation():
    hypothesis = "Explica solo la mitad."
    evidence = ["e1", "e2", "e3", "e4"]
    constraints = {"explains": ["e1", "e2"], "contradicts": []}
    # C = 2 explained / (2 + 0 + 2 unexplained) = 0.5.
    assert explanatory_coherence(hypothesis, evidence, constraints) == 0.5


def test_explanatory_coherence_penalizes_contradicted_evidence():
    hypothesis = "Explica una y contradice otra."
    evidence = ["e1", "e2", "e3"]
    constraints = {"explains": ["e1"], "contradicts": ["e2"]}
    # C = 1 / (1 + 1 + 2) = 0.25.
    assert explanatory_coherence(hypothesis, evidence, constraints) == 0.25


def test_explanatory_coherence_consistency_with_competing_hypotheses():
    evidence = ["e1"]
    consistent = {
        "explains": ["e1"],
        "contradicts": [],
        "coherent_with": ["h2"],
        "incoherent_with": [],
    }
    inconsistent = {
        "explains": ["e1"],
        "contradicts": [],
        "coherent_with": [],
        "incoherent_with": ["h3"],
    }
    # Consistency with h2 adds a satisfied positive constraint -> C = 1.0;
    # inconsistency with h3 adds a violated negative -> C = 1/(1+1) = 0.5.
    assert explanatory_coherence("h1", evidence, consistent) == 1.0
    assert explanatory_coherence("h1", evidence, inconsistent) == 0.5


def test_explanatory_coherence_neutral_without_scope():
    # No evidence in scope -> neutral 0.5 (no facts to evaluate, documented).
    assert explanatory_coherence("h", [], {"explains": ["e1"]}) == 0.5


def test_calibration_params_defaults_are_fixed_a_priori():
    params = CalibrationParams()
    assert params.alpha == 0.5
    assert params.M == 10
    assert params.L0 == 0.0