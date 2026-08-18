"""Unit tests for the explanatory coherence competition (P2).

One test per mental model (positive: the correct model wins; negative: a
foreign model does not) plus scoring-by-weight/quality and the documented
deterministic tie-break. Synthetic immutable Evidence only - no database.
"""
import uuid

import pytest
from libs.perception.context import (
    PURPOSE_CAPACITY_MANAGEMENT,
    PURPOSE_INFRASTRUCTURE_HEALTH,
    PURPOSE_SECURITY_POSTURE,
    build_context,
    context_id,
    models_for_purpose,
)
from libs.perception.evidence import Evidence
from libs.perception.observation import QualityClass

from src.activator.coherence import compete, weights_by_type
from src.activator.engine import ActivatorEngine

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")

# organization_type -> (winning mental model, purpose where it competes)
EXPECTED: dict[str, tuple[str, str]] = {
    "resource_exhaustion_evidence": ("resource_pressure", PURPOSE_INFRASTRUCTURE_HEALTH),
    "service_degradation_evidence": ("service_failure", PURPOSE_INFRASTRUCTURE_HEALTH),
    "auth_anomaly_evidence": ("auth_compromise", PURPOSE_SECURITY_POSTURE),
    "backup_failure_evidence": ("capacity_risk", PURPOSE_INFRASTRUCTURE_HEALTH),
    "vmware_capacity_evidence": ("capacity_risk", PURPOSE_INFRASTRUCTURE_HEALTH),
    "network_anomaly_evidence": ("connectivity_degradation", PURPOSE_INFRASTRUCTURE_HEALTH),
}


def make_evidence(org_type, weight=0.88, quality=QualityClass.Q1) -> Evidence:
    return Evidence(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        observation_ids=[uuid.uuid4()],
        organization_type=org_type,
        description="factual organization",
        quality_class=quality,
        weight=weight,
    )


@pytest.mark.parametrize("org_type,expected", EXPECTED.items())
def test_each_mental_model_wins_on_its_own_evidence(org_type, expected):
    expected_model, purpose = expected
    result = compete([make_evidence(org_type)], purpose)
    assert result is not None
    assert result.winner.mental_model_id == expected_model
    assert result.winner.coherence_score == pytest.approx(1.0)


def test_capacity_risk_explains_both_capacity_domains():
    batch = [
        make_evidence("backup_failure_evidence", weight=0.88),
        make_evidence("vmware_capacity_evidence", weight=0.63),
    ]
    result = compete(batch, PURPOSE_CAPACITY_MANAGEMENT)
    assert result.winner.mental_model_id == "capacity_risk"
    assert result.winner.coherence_score == pytest.approx(1.0)
    assert len(result.evidence_ids) == 2


@pytest.mark.parametrize("org_type,expected", EXPECTED.items())
def test_foreign_models_do_not_win_on_another_domain(org_type, expected):
    expected_model, purpose = expected
    batch = [make_evidence(org_type)]
    result = compete(batch, purpose)
    assert result.winner.mental_model_id == expected_model
    rivals = [c for c in result.candidates if c.mental_model_id != expected_model]
    assert all(rival.coherence_score == pytest.approx(0.0) for rival in rivals)


def test_score_weights_evidence_by_quality_class():
    batch = [
        make_evidence("resource_exhaustion_evidence", weight=0.88, quality=QualityClass.Q1),
        make_evidence("network_anomaly_evidence", weight=0.63, quality=QualityClass.Q2),
    ]
    result = compete(batch, PURPOSE_INFRASTRUCTURE_HEALTH)
    by_model = {c.mental_model_id: c.coherence_score for c in result.candidates}
    assert by_model["resource_pressure"] == pytest.approx(0.88 / 1.51, abs=0.0001)
    assert by_model["connectivity_degradation"] == pytest.approx(0.63 / 1.51, abs=0.0001)
    assert result.winner.mental_model_id == "resource_pressure"


@pytest.mark.parametrize(
    "purpose",
    [PURPOSE_INFRASTRUCTURE_HEALTH, PURPOSE_SECURITY_POSTURE, PURPOSE_CAPACITY_MANAGEMENT],
)
def test_p2_confrontation_every_purpose_has_at_least_two_candidates(purpose):
    # P2 requires selection against the strongest alternative: no purpose may
    # have a single candidate that would win by default (confirmation, not
    # selection). Adding a new purpose or mental model must keep >= 2 rivals.
    candidates = models_for_purpose(purpose)
    assert len(candidates) >= 2, f"purpose {purpose!r} has only {len(candidates)} candidate(s)"


def test_weights_by_type_accumulates_same_type():
    batch = [
        make_evidence("resource_exhaustion_evidence"),
        make_evidence("resource_exhaustion_evidence"),
    ]
    weights = weights_by_type(batch)
    assert weights["resource_exhaustion_evidence"] == pytest.approx(1.76)


def test_tie_breaks_deterministically_by_model_id():
    batch = [
        make_evidence("resource_exhaustion_evidence"),
        make_evidence("service_degradation_evidence"),
    ]
    result = compete(batch, PURPOSE_INFRASTRUCTURE_HEALTH)
    scores = sorted(
        (c.mental_model_id, c.coherence_score) for c in result.candidates
    )
    tied = [model_id for model_id, score in scores if score == pytest.approx(0.5)]
    assert set(tied) == {"resource_pressure", "service_failure"}
    assert result.winner.mental_model_id == "resource_pressure"
    again = compete(batch, PURPOSE_INFRASTRUCTURE_HEALTH)
    assert again.winner.mental_model_id == result.winner.mental_model_id


def test_compete_returns_none_without_evidence():
    assert compete([], PURPOSE_INFRASTRUCTURE_HEALTH) is None


def test_compete_returns_none_without_compatible_models():
    batch = [make_evidence("resource_exhaustion_evidence")]
    assert compete(batch, "purpose_with_no_models") is None


def test_every_purpose_has_at_least_two_candidates():
    purposes = (
        PURPOSE_INFRASTRUCTURE_HEALTH,
        PURPOSE_SECURITY_POSTURE,
        PURPOSE_CAPACITY_MANAGEMENT,
    )
    for purpose in purposes:
        assert len(models_for_purpose(purpose)) >= 2


def test_competing_models_records_candidates_without_inventing_fields():
    batch = [
        make_evidence("resource_exhaustion_evidence"),
        make_evidence("network_anomaly_evidence"),
    ]
    engine = ActivatorEngine()
    create = engine.activate(batch, PURPOSE_INFRASTRUCTURE_HEALTH)
    assert create is not None
    ids = [c["mental_model_id"] for c in create.competing_models]
    assert set(ids) == {
        "resource_pressure",
        "service_failure",
        "capacity_risk",
        "connectivity_degradation",
    }
    assert create.mental_model_id in ids
    for candidate in create.competing_models:
        assert sorted(candidate) == ["coherence_score", "mental_model_id"]

    winner = next(
        c
        for c in create.competing_models
        if c["mental_model_id"] == create.mental_model_id
    )
    losers = [c for c in create.competing_models if c["mental_model_id"] != create.mental_model_id]
    assert all(loser["coherence_score"] <= winner["coherence_score"] for loser in losers)


def test_activate_returns_none_without_evidence():
    assert ActivatorEngine().activate([], PURPOSE_INFRASTRUCTURE_HEALTH) is None


def test_context_id_is_deterministic_and_content_addressed():
    ids = [uuid.uuid4(), uuid.uuid4()]
    first = context_id(TENANT, PURPOSE_CAPACITY_MANAGEMENT, ids)
    second = context_id(TENANT, PURPOSE_CAPACITY_MANAGEMENT, list(reversed(ids)))
    assert first == second
    other_ev = context_id(TENANT, PURPOSE_CAPACITY_MANAGEMENT, [uuid.uuid4()])
    assert first != other_ev
    other_purpose = context_id(TENANT, PURPOSE_INFRASTRUCTURE_HEALTH, ids)
    assert first != other_purpose


def test_build_context_is_stable_and_carries_competition():
    engine = ActivatorEngine()
    batch = [
        make_evidence("backup_failure_evidence"),
        make_evidence("resource_exhaustion_evidence"),
    ]
    create = engine.activate(batch, PURPOSE_INFRASTRUCTURE_HEALTH)
    first = build_context(create)
    second = build_context(create)
    assert first.id == second.id
    assert first.mental_model_id == create.mental_model_id
    assert first.coherence_score == create.coherence_score
    assert first.competing_models == create.competing_models
    assert first.is_active is True