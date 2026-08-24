"""Phase 11 — Decision/Execution Separation tests."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.action.executor import (
    NON_EXECUTING_CAPABILITIES,
    validate_execution_authorization,
    validate_no_direct_execution,
)


def test_observation_cannot_execute():
    """Phase 11: observation must never execute actions directly."""
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("observation")


def test_hypothesis_cannot_execute():
    """Phase 11: hypothesis must never execute actions directly."""
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("hypothesis")


def test_pattern_cannot_execute():
    """Phase 11: pattern must never execute actions directly."""
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("pattern")


def test_anomaly_cannot_execute():
    """Phase 11: anomaly must never execute actions directly."""
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("anomaly")


def test_insight_cannot_execute():
    """Phase 11: insight must never execute actions directly."""
    with pytest.raises(ValueError, match="must not execute actions directly"):
        validate_no_direct_execution("insight")


def test_decision_can_execute_via_authorization():
    """Phase 11: decision is not in the non-executing set."""
    # decision is NOT in NON_EXECUTING_CAPABILITIES
    assert "decision" not in NON_EXECUTING_CAPABILITIES


def test_execution_authorization_requires_execute_permission():
    """Phase 11: executor must have execute permission."""
    # viewer cannot execute
    assert not validate_execution_authorization(
        decision_role="admin",
        executor_role="viewer",
        risk_tolerance="low",
    )


def test_admin_cannot_execute():
    """Phase 11: admin can commit but not execute."""
    assert not validate_execution_authorization(
        decision_role="admin",
        executor_role="admin",
        risk_tolerance="low",
    )


def test_superadmin_can_execute_low_risk():
    """Phase 11: superadmin can execute low risk."""
    assert validate_execution_authorization(
        decision_role="superadmin",
        executor_role="superadmin",
        risk_tolerance="low",
    )


def test_superadmin_can_execute_high_risk():
    """Phase 11: superadmin can execute high risk."""
    assert validate_execution_authorization(
        decision_role="superadmin",
        executor_role="superadmin",
        risk_tolerance="high",
    )
