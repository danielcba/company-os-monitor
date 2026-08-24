"""Phase 10 — Cognitive Boundary 2.0 tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.capability_policy import (
    CAPABILITY_POLICIES,
    CapabilityPolicy,
    DefaultPolicyStore,
    validate_authority,
    validate_capability_transition,
    validate_confidence_requirement,
)


def test_all_capabilities_have_policies():
    """Phase 10: every cognitive concept has a declarative policy."""
    expected = {
        "observation", "evidence", "context",
        "pattern", "anomaly", "hypothesis", "insight",
        "confidence",
        "recommendation", "decision", "execution",
    }
    assert set(CAPABILITY_POLICIES.keys()) == expected


def test_perception_family():
    """Phase 10: perception capabilities don't require confidence."""
    for cap in ["observation", "evidence", "context"]:
        policy = CAPABILITY_POLICIES[cap]
        assert policy.family == "perception"
        assert policy.confidence_required is False
        assert policy.tenant_scoped is True


def test_reasoning_family():
    """Phase 10: reasoning capabilities don't require confidence."""
    for cap in ["pattern", "anomaly", "hypothesis", "insight"]:
        policy = CAPABILITY_POLICIES[cap]
        assert policy.family == "reasoning"
        assert policy.confidence_required is False


def test_action_family_requires_confidence():
    """Phase 10: recommendation and decision require confidence (R4)."""
    for cap in ["recommendation", "decision"]:
        policy = CAPABILITY_POLICIES[cap]
        assert policy.family == "action"
        assert policy.confidence_required is True


def test_decision_has_execution_authority():
    """Phase 10: decision defines execution_authority for Phase 11."""
    policy = CAPABILITY_POLICIES["decision"]
    assert policy.execution_authority == "execute"


def test_observation_to_evidence_allowed():
    """Phase 10: observation → evidence is a valid transition."""
    assert validate_capability_transition("observation", "evidence")


def test_context_to_pattern_allowed():
    """Phase 10: context → pattern is a valid transition."""
    assert validate_capability_transition("context", "pattern")


def test_hypothesis_to_insight_allowed():
    """Phase 10: hypothesis → insight is a valid transition."""
    assert validate_capability_transition("hypothesis", "insight")


def test_observation_to_action_blocked():
    """Phase 10: observation → recommendation is NOT allowed."""
    assert not validate_capability_transition("observation", "recommendation")


def test_pattern_to_decision_blocked():
    """Phase 10: pattern → decision is NOT allowed."""
    assert not validate_capability_transition("pattern", "decision")


def test_anomaly_to_recommendation_blocked():
    """Phase 10: anomaly → recommendation is NOT allowed (must go through hypothesis)."""
    assert not validate_capability_transition("anomaly", "recommendation")


def test_recommendation_to_decision_allowed():
    """Phase 10: recommendation → decision is allowed."""
    assert validate_capability_transition("recommendation", "decision")


def test_confidence_required_for_propose():
    """Phase 10: recommendation requires confidence."""
    assert validate_confidence_requirement("recommendation")


def test_confidence_not_required_for_observation():
    """Phase 10: observation does NOT require confidence."""
    assert not validate_confidence_requirement("observation")


def test_viewer_cannot_propose():
    """Phase 10: viewer cannot propose (needs propose permission)."""
    assert not validate_authority("recommendation", "viewer")


def test_admin_can_propose():
    """Phase 10: admin can propose."""
    assert validate_authority("recommendation", "admin")


def test_superadmin_can_execute():
    """Phase 10: superadmin can execute."""
    assert validate_authority("execution", "superadmin")


def test_admin_cannot_execute():
    """Phase 10: admin cannot execute (only superadmin can)."""
    assert not validate_authority("execution", "admin")


def test_default_policy_store():
    """Phase 10: DefaultPolicyStore returns correct policies."""
    store = DefaultPolicyStore()
    assert store.get_policy("observation") is not None
    assert store.get_policy("nonexistent") is None
    assert len(store.get_all_policies()) == len(CAPABILITY_POLICIES)
