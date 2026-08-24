"""14 - Policy Bypass: boundary rules must be enforced.

Enforces: R3 (Cognitive Boundary), R4 (confidence requirement).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "gateway" / "api-gateway"))


def test_canonical_flow_valid_transitions():
    """Only direct successors in the canonical flow are allowed."""
    from src.boundary import is_canonical_flow

    assert is_canonical_flow("observation", "evidence")
    assert is_canonical_flow("evidence", "context")
    assert is_canonical_flow("context", "pattern")
    assert is_canonical_flow("pattern", "anomaly")
    assert is_canonical_flow("anomaly", "hypothesis")
    assert is_canonical_flow("hypothesis", "insight")
    assert is_canonical_flow("insight", "recommendation")
    assert is_canonical_flow("recommendation", "decision")
    assert is_canonical_flow("decision", "execution")


def test_canonical_flow_invalid_transitions():
    """Shortcuts must be rejected."""
    from src.boundary import is_canonical_flow

    assert not is_canonical_flow("observation", "action")
    assert not is_canonical_flow("pattern", "recommendation")
    assert not is_canonical_flow("anomaly", "decision")
    assert not is_canonical_flow("hypothesis", "execution")
    assert not is_canonical_flow("context", "recommendation")


def test_boundary_gate_missing_confidence():
    """Propose/commit without confidence_id must be rejected."""
    from src.boundary import boundary_gate

    assert boundary_gate("propose", {}) == "missing_confidence"
    assert boundary_gate("commit", {}) == "missing_confidence"
    assert boundary_gate("propose", {"confidence_score": 0.9}) == "missing_confidence"


def test_boundary_gate_with_confidence():
    """Propose/commit with confidence_id must pass structural check."""
    from src.boundary import boundary_gate

    assert boundary_gate("propose", {"confidence_id": "test-uuid"}) == "ok"
    assert boundary_gate("commit", {"confidence_id": "test-uuid"}) == "ok"


def test_boundary_gate_unknown_action():
    """Unknown action must be rejected."""
    from src.boundary import boundary_gate

    assert boundary_gate("unknown", {}) == "unknown_action"
    assert boundary_gate("hack", {"confidence_id": "x"}) == "unknown_action"


def test_read_never_requires_confidence():
    """Read actions must never require confidence."""
    from src.boundary import boundary_gate

    assert boundary_gate("read", {}) == "ok"
    assert boundary_gate("read", {"confidence_id": "x"}) == "ok"


def test_ack_never_requires_confidence():
    """Ack actions must never require confidence."""
    from src.boundary import boundary_gate

    assert boundary_gate("ack", {}) == "ok"


def test_check_boundary_raises_on_violation():
    """check_boundary must raise BoundaryViolationError on violations."""
    from src.boundary import BoundaryViolationError, check_boundary

    with pytest.raises(BoundaryViolationError):
        check_boundary("unknown_action", {})
    with pytest.raises(BoundaryViolationError):
        check_boundary("propose", {})
    with pytest.raises(BoundaryViolationError):
        check_boundary("commit", {})


def test_check_boundary_passes_valid():
    """check_boundary must pass for valid actions."""
    from src.boundary import check_boundary

    check_boundary("read", {})
    check_boundary("ack", {})
    check_boundary("propose", {"confidence_id": "test"})
    check_boundary("commit", {"confidence_id": "test"})
