"""Phase 19 — Learning/P7 tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.action.decision import compare_expected_actual_outcomes

# Test constants for assertions.
BRIER_TOLERANCE = 0.01
EXPECTED_OUTCOME_COUNT = 2


def test_compare_empty_outcomes():
    """Phase 19: empty expected outcomes returns zero scores."""
    result = compare_expected_actual_outcomes([], None)
    assert result["brier_score"] == 0.0
    assert result["ece"] == 0.0
    assert result["outcome_count"] == 0


def test_compare_perfect_prediction():
    """Phase 19: perfect prediction (1.0) matching actual (1) gives brier=0."""
    expected = [
        {"prediction": "1.0", "verifiable_by": "cpu_usage", "deadline": "2026-12-31"}
    ]
    actual = [
        {"verifiable_by": "cpu_usage", "value": True}
    ]
    result = compare_expected_actual_outcomes(expected, actual)
    assert result["brier_score"] == 0.0
    assert result["outcome_count"] == 1
    assert result["details"][0]["matches"] is True


def test_compare_wrong_prediction():
    """Phase 19: wrong prediction (1.0) with actual (0) gives brier=1.0."""
    expected = [
        {"prediction": "1.0", "verifiable_by": "cpu_usage", "deadline": "2026-12-31"}
    ]
    actual = [
        {"verifiable_by": "cpu_usage", "value": False}
    ]
    result = compare_expected_actual_outcomes(expected, actual)
    assert result["brier_score"] == 1.0
    assert result["details"][0]["matches"] is False


def test_compare_partial_prediction():
    """Phase 19: partial prediction (0.7) with actual (1) gives brier=0.09."""
    expected = [
        {"prediction": "0.7", "verifiable_by": "cpu_usage", "deadline": "2026-12-31"}
    ]
    actual = [
        {"verifiable_by": "cpu_usage", "value": True}
    ]
    result = compare_expected_actual_outcomes(expected, actual)
    assert abs(result["brier_score"] - 0.09) < BRIER_TOLERANCE
    assert result["details"][0]["matches"] is True


def test_compare_missing_actual_outcome():
    """Phase 19: missing actual outcome is marked as unavailable."""
    expected = [
        {"prediction": "0.8", "verifiable_by": "memory_usage", "deadline": "2026-12-31"}
    ]
    result = compare_expected_actual_outcomes(expected, None)
    assert result["outcome_count"] == 1
    assert result["details"][0]["available"] is False


def test_compare_multiple_outcomes():
    """Phase 19: multiple outcomes are compared independently."""
    expected = [
        {"prediction": "1.0", "verifiable_by": "cpu_usage", "deadline": "2026-12-31"},
        {"prediction": "0.0", "verifiable_by": "disk_usage", "deadline": "2026-12-31"},
    ]
    actual = [
        {"verifiable_by": "cpu_usage", "value": True},
        {"verifiable_by": "disk_usage", "value": False},
    ]
    result = compare_expected_actual_outcomes(expected, actual)
    assert result["brier_score"] == 0.0
    assert result["outcome_count"] == EXPECTED_OUTCOME_COUNT
