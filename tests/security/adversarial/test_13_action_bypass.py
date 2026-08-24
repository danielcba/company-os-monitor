"""13 - Action Bypass: cognitive capabilities must not directly execute.

Enforces: R1 (one capability per component), P6 (deliberate action).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


def test_observation_cannot_execute():
    """Observation must never execute actions directly."""
    from libs.action.executor import validate_no_direct_execution
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("observation")


def test_pattern_cannot_execute():
    """Pattern must never execute actions directly."""
    from libs.action.executor import validate_no_direct_execution
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("pattern")


def test_anomaly_cannot_execute():
    """Anomaly must never execute actions directly."""
    from libs.action.executor import validate_no_direct_execution
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("anomaly")


def test_hypothesis_cannot_execute():
    """Hypothesis must never execute actions directly."""
    from libs.action.executor import validate_no_direct_execution
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("hypothesis")


def test_insight_cannot_execute():
    """Insight must never execute actions directly."""
    from libs.action.executor import validate_no_direct_execution
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("insight")


def test_context_cannot_execute():
    """Context must never execute actions directly."""
    from libs.action.executor import validate_no_direct_execution
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("context")


def test_evidence_cannot_execute():
    """Evidence must never execute actions directly."""
    from libs.action.executor import validate_no_direct_execution
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("evidence")


def test_decision_not_in_non_executing_set():
    """Decision IS allowed in the action layer (it commits, not reasons)."""
    from libs.action.executor import NON_EXECUTING_CAPABILITIES
    assert "decision" not in NON_EXECUTING_CAPABILITIES


def test_recommendation_not_in_non_executing_set():
    """Recommendation IS allowed in the action layer (it proposes)."""
    from libs.action.executor import NON_EXECUTING_CAPABILITIES
    assert "recommendation" not in NON_EXECUTING_CAPABILITIES
