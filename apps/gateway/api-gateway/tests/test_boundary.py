"""Unit tests for the Cognitive Boundary rules (R3, pure, no I/O)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.boundary import (
    CANONICAL_FLOW,
    BoundaryViolationError,
    check_boundary,
    is_canonical_flow,
    validate_confidence_present,
)


def test_canonical_flow_adjacency_complete():
    # Every concept may only advance to its DIRECT successor (no shortcuts).
    assert CANONICAL_FLOW["observation"] == {"evidence"}
    assert CANONICAL_FLOW["evidence"] == {"context"}
    assert CANONICAL_FLOW["context"] == {"pattern"}
    assert CANONICAL_FLOW["pattern"] == {"anomaly"}
    assert CANONICAL_FLOW["anomaly"] == {"hypothesis"}
    assert CANONICAL_FLOW["hypothesis"] == {"insight"}
    assert CANONICAL_FLOW["insight"] == {"recommendation"}
    assert CANONICAL_FLOW["recommendation"] == {"decision"}
    assert CANONICAL_FLOW["decision"] == {"execution"}


def test_is_canonical_flow_true_for_direct_successors():
    assert is_canonical_flow("evidence", "context")
    assert is_canonical_flow("recommendation", "decision")


def test_is_canonical_flow_blocks_shortcuts():
    # R3: raw observations never reach Reasoning/Action; patterns/anomalies/
    # hypotheses never trigger actions directly; no bypass of confidence/action.
    assert not is_canonical_flow("observation", "action")
    assert not is_canonical_flow("observation", "context")
    assert not is_canonical_flow("pattern", "alert")
    assert not is_canonical_flow("anomaly", "recommendation")
    assert not is_canonical_flow("hypothesis", "decision")
    assert is_canonical_flow("decision", "execution")


def test_unknown_concept_has_no_outgoing_flow():
    assert not is_canonical_flow("alert", "decision")


def test_confidence_required_for_propose_and_commit():
    assert validate_confidence_present({"confidence_score": 0.8})
    assert validate_confidence_present({"confidence_id": "u-1"})
    assert not validate_confidence_present({})
    assert not validate_confidence_present(None)
    assert not validate_confidence_present({"confidence_id": None})


def test_check_boundary_missing_confidence_raises_for_commit():
    with pytest.raises(BoundaryViolationError, match="Confidence"):
        check_boundary("commit", {})
    with pytest.raises(BoundaryViolationError, match="Confidence"):
        check_boundary("propose", {"action": "restart"})


def test_check_boundary_commit_with_confidence_ok():
    check_boundary("commit", {"confidence_score": 0.85, "risk_tolerance": "low"})


def test_check_boundary_ack_does_not_require_confidence():
    check_boundary("ack", {})


def test_check_boundary_unknown_action_raises():
    with pytest.raises(BoundaryViolationError, match="not a declared pipeline"):
        check_boundary("ban_users", {"confidence_score": 0.9})