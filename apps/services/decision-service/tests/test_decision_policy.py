"""Unit tests for the Decision Policy Library (Procedural Memory, declarative).

Covers the frozen/versioned ``DecisionPolicyEntry``, the canonical catalogue
thresholds (docs/03: "> 0.75 to commit; > 0.9 for irreversible"), the per-domain
risk tolerance declarations and the threshold overrides applied at deployment.
No I/O: pure model tests.
"""
from dataclasses import FrozenInstanceError

import pytest
from libs.procedural_memory.action_space import DOMAINS
from libs.procedural_memory.decision_policy import (
    DECISION_POLICIES,
    DECISION_POLICY_LIBRARY,
    POLICY_BY_DOMAIN,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_TOLERANCES,
    DecisionPolicyEntry,
    apply_threshold_overrides,
    select_policy,
)


def test_catalogue_covers_all_domains_with_versioned_policy():
    assert {entry.domain for entry in DECISION_POLICY_LIBRARY} == set(DOMAINS)
    for entry in DECISION_POLICY_LIBRARY:
        assert entry.policy_id.endswith("_v1")
        assert entry.policy_id.startswith(entry.domain)
    assert len(DECISION_POLICIES) == len(DECISION_POLICY_LIBRARY)
    assert len(POLICY_BY_DOMAIN) == len(DOMAINS)


def test_policy_entries_are_frozen_and_unique():
    seen = set()
    for entry in DECISION_POLICY_LIBRARY:
        assert entry.policy_id not in seen
        seen.add(entry.policy_id)
    with pytest.raises(FrozenInstanceError):
        DECISION_POLICY_LIBRARY[0].policy_id = "x"  # type: ignore[misc]


def test_canonical_thresholds_from_docs03():
    for entry in DECISION_POLICY_LIBRARY:
        assert entry.min_confidence_for_commit == 0.75
        assert entry.min_confidence_irreversible == 0.9
        assert entry.min_confidence_irreversible >= entry.min_confidence_for_commit


def test_risk_tolerance_declarations_per_domain():
    compute = POLICY_BY_DOMAIN["compute"]
    assert RISK_HIGH not in compute.allowed_risk_tolerance
    assert RISK_MEDIUM in compute.allowed_risk_tolerance
    storage = POLICY_BY_DOMAIN["storage"]
    assert {RISK_LOW, RISK_MEDIUM, RISK_HIGH} <= storage.allowed_risk_tolerance
    for entry in DECISION_POLICY_LIBRARY:
        assert entry.allowed_risk_tolerance <= RISK_TOLERANCES
        assert entry.allowed_risk_tolerance


def test_policy_requires_authority_by_default():
    for entry in DECISION_POLICY_LIBRARY:
        assert entry.requires_authority is True


def test_select_policy_resolves_by_domain():
    assert select_policy(None, "security").policy_id == "security_commit_v1"
    assert select_policy(None, "unknown_domain") is None
    assert select_policy(None, None) is None


def test_apply_threshold_overrides_returns_new_frozen_entry():
    storage = POLICY_BY_DOMAIN["storage"]
    overridden = apply_threshold_overrides(storage, 0.8, 0.95)
    assert overridden.min_confidence_for_commit == 0.8
    assert overridden.min_confidence_irreversible == 0.95
    assert overridden.allowed_risk_tolerance == storage.allowed_risk_tolerance
    # the canonical catalogue is NOT mutated (procedural memory immutable)
    assert storage.min_confidence_for_commit == 0.75
    assert overridden.policy_id == storage.policy_id


def test_apply_threshold_overrides_noop_when_none():
    storage = POLICY_BY_DOMAIN["storage"]
    assert apply_threshold_overrides(storage) is storage


def test_entry_validation_failures():
    with pytest.raises(ValueError):
        DecisionPolicyEntry("x_v1", "not_a_domain")
    with pytest.raises(ValueError):
        DecisionPolicyEntry("", "storage")
    with pytest.raises(ValueError):
        DecisionPolicyEntry("x_v1", "storage", min_confidence_for_commit=1.5)
    with pytest.raises(ValueError):
        DecisionPolicyEntry("x_v1", "storage", min_confidence_irreversible=0.5)
    with pytest.raises(ValueError):
        DecisionPolicyEntry(
            "x_v1", "storage", allowed_risk_tolerance=frozenset({"extreme"})
        )
    with pytest.raises(ValueError):
        DecisionPolicyEntry(
            "x_v1", "storage", allowed_risk_tolerance=frozenset()
        )