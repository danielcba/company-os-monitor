"""Unit tests for the Decision Committer (pure, no I/O - Action/Commit).

Covers the Cognitive Contract of the Decision concept: one test per declared
policy (recommendation with Confidence >= threshold -> committed Decision with
falsifiable expected_outcomes; Confidence < threshold -> NOT committed), the
falsifiability rule (R5/Popper: every outcome carries prediction + verifiable_by
+ deadline in observable terms), P6 (the Decision is RECORDED, never executed),
anti-indefinition (commitment is a definitive sentence, never a vague intention),
deterministic dedup and full traceability binding.
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from libs.action.decision import (
    OUTCOME_DEADLINE,
    OUTCOME_PREDICTION,
    OUTCOME_VERIFIABLE_BY,
    STATUS_COMMITTED,
    build_decision,
)
from libs.action.recommendation import STATUS_PROPOSED, Recommendation
from libs.learning.confidence import Confidence
from libs.procedural_memory.action_space import ACTION_SPACE_LIBRARY
from libs.procedural_memory.decision_policy import (
    POLICY_BY_DOMAIN,
    RISK_HIGH,
    RISK_MEDIUM,
)

from src.committer import (
    BELOW_CONFIDENCE,
    COMMITTABLE,
    NO_AUTHORITY,
    NO_POLICY,
    RISK_NOT_ALLOWED,
    Authority,
    build_commitment,
    build_expected_outcomes,
    commit,
    commit_eligibility,
    policy_authority_id,
    recommendation_domain,
    resolve_risk_tolerance,
)

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
HYPOTHESIS = uuid.UUID("11111111-1111-1111-1111-111111111101")
RECOMMENDATION = uuid.UUID("22222222-2222-2222-2222-222222222201")
CONFIDENCE = uuid.UUID("33333333-3333-3333-3333-333333333301")
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

EXPAND_DESCRIPTION = (
    "Expandir el volumen objetivo del almacenamiento antes del umbral "
    "proyectado, o mover los datos a un destino con espacio disponible."
)


def make_recommendation(domain="storage", confidence_score=0.75, **overrides):
    entry = next(e for e in ACTION_SPACE_LIBRARY if e.domain == domain)
    actions = sorted(entry.allowed_actions)
    leading = actions[0]
    alternatives = [
        {
            "action": action,
            "rationale": "Opción considerada dentro del action space explícito.",
            "rejected_reason": "No elegida como acción principal en esta formulación.",
            "confidence": confidence_score,
        }
        for action in actions[1:]
    ]
    base = {
        "id": RECOMMENDATION,
        "tenant_id": TENANT,
        "hypothesis_id": HYPOTHESIS,
        "insight_id": None,
        "confidence_id": CONFIDENCE,
        "action_description": EXPAND_DESCRIPTION if domain == "storage" else (
            f"Ejecutar {leading} de forma definitiva dentro del alcance documentado."
        ),
        "rationale": "Derivada de la hipótesis y su confidence calibrada.",
        "expected_consequences": [
            (
                "El espacio libre del volumen objetivo permanecerá por encima del "
                "umbral documentado durante los próximos 90 días."
            )
        ],
        "alternatives_considered": alternatives,
        "confidence_score": confidence_score,
        "status": STATUS_PROPOSED,
        "proposed_at": NOW,
    }
    base.update(overrides)
    return Recommendation(**base)


def make_confidence(confidence_score=0.75, **overrides):
    base = {
        "id": CONFIDENCE,
        "tenant_id": TENANT,
        "target_type": "hypothesis",
        "target_id": HYPOTHESIS,
        "evidential_support": 0.7,
        "explanatory_coherence": 0.8,
        "historical_calibration": 1.0,
        "confidence_score": confidence_score,
        "alpha": 0.5,
        "calibration_justification": "S=0.7000, C=0.8000, ECE=0.0000, C_final=0.7500.",
        "calibration_error_estimate": 0.0,
        "computed_at": NOW,
    }
    base.update(overrides)
    return Confidence(**base)


def make_authority(policy, risk_tolerance=RISK_MEDIUM):
    return Authority(
        authority_id=policy_authority_id(policy.policy_id),
        label=f"policy:{policy.policy_id}",
        risk_tolerance=risk_tolerance,
    )


# ---------------------------------------------------------------------------
# One test per declared policy: commit when Confidence >= threshold.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "domain",
    ["storage", "compute", "security", "backup", "network", "observability"],
)
def test_commit_per_policy(domain):
    policy = POLICY_BY_DOMAIN[domain]
    recommendation = make_recommendation(domain=domain, confidence_score=0.8)
    confidence = make_confidence(confidence_score=0.8)
    authority = make_authority(policy)
    create = commit(recommendation, confidence, policy, authority)
    assert create is not None
    assert create.status == STATUS_COMMITTED
    assert create.risk_tolerance == RISK_MEDIUM
    assert create.authority_id == authority.authority_id
    assert create.recommendation_id == recommendation.id
    assert create.confidence_id == recommendation.confidence_id
    for outcome in create.expected_outcomes:
        assert {OUTCOME_PREDICTION, OUTCOME_VERIFIABLE_BY, OUTCOME_DEADLINE} <= set(
            outcome
        )


@pytest.mark.parametrize(
    "domain",
    ["storage", "compute", "security", "backup", "network", "observability"],
)
def test_negative_below_confidence_per_policy(domain):
    policy = POLICY_BY_DOMAIN[domain]
    recommendation = make_recommendation(domain=domain, confidence_score=0.7)
    confidence = make_confidence(confidence_score=0.7)
    authority = make_authority(policy)
    assert (
        commit_eligibility(recommendation, confidence, policy, authority)
        == BELOW_CONFIDENCE
    )
    assert commit(recommendation, confidence, policy, authority) is None


def test_eligibility_at_threshold_is_committable():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation(confidence_score=0.75)
    confidence = make_confidence(confidence_score=0.75)
    authority = make_authority(policy, risk_tolerance=RISK_MEDIUM)
    assert commit_eligibility(recommendation, confidence, policy, authority) == COMMITTABLE
    assert commit(recommendation, confidence, policy, authority) is not None


# ---------------------------------------------------------------------------
# Falsifiability (R5 / Popper): outcomes observable, verifiable, dated.
# ---------------------------------------------------------------------------
def test_expected_outcomes_are_falsifiable_in_observable_terms():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation()
    confidence = make_confidence()
    create = commit(recommendation, confidence, policy, make_authority(policy))
    assert create is not None
    assert create.expected_outcomes
    for outcome in create.expected_outcomes:
        assert outcome[OUTCOME_PREDICTION].strip()
        assert outcome[OUTCOME_VERIFIABLE_BY].strip()
        assert outcome[OUTCOME_DEADLINE].strip()
    assert create.expected_outcomes[0][OUTCOME_VERIFIABLE_BY] == "disk_free_percent"


def test_expected_outcome_deadline_is_committed_at_plus_domain_window():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation()
    outcomes = build_expected_outcomes(recommendation, policy, NOW)
    # storage window = 90 days (docs/05: 30/60/90 day learning loop)
    assert outcomes[0][OUTCOME_DEADLINE] == (NOW + timedelta(days=90)).date().isoformat()


def test_commit_requires_falsifiable_outcomes():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation(expected_consequences=[])
    with pytest.raises(ValueError):
        build_expected_outcomes(recommendation, policy, NOW)


# ---------------------------------------------------------------------------
# P6: the Decision is RECORDED, never executed.
# ---------------------------------------------------------------------------
def test_decision_is_recorded_not_executed():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation()
    confidence = make_confidence()
    create = commit(recommendation, confidence, policy, make_authority(policy))
    assert create is not None
    assert create.status == STATUS_COMMITTED
    assert create.executed_at is None
    assert create.actual_outcomes is None
    # Pure: inputs are not mutated and nothing is executed (no I/O available).
    assert create.commitment


# ---------------------------------------------------------------------------
# Anti-indefinition: commitment is a definitive sentence.
# ---------------------------------------------------------------------------
def test_commitment_is_definitive_not_vague_intention():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation()
    confidence = make_confidence()
    create = commit(recommendation, confidence, policy, make_authority(policy))
    assert create is not None
    commitment = create.commitment
    # The trailing alternative clause ("o mover los datos...") is dropped: the
    # commitment selects a DEFINITE course of action (the concept: "Let's keep
    # an eye on it." is a Non-example).
    assert " o " not in commitment
    assert "keep an eye" not in commitment.lower()
    assert "probably" not in commitment.lower()
    assert "pendientes" not in commitment.lower()
    assert "probablemente" not in commitment.lower()
    assert commitment.startswith(
        "Expandir el volumen objetivo del almacenamiento antes del umbral proyectado."
    )
    # owner (authority) + timeline (deadline) present per the concept.
    assert "autoridad" in commitment
    assert "evaluados en" in commitment


def test_build_commitment_includes_authority_and_deadline():
    policy = POLICY_BY_DOMAIN["storage"]
    authority = make_authority(policy)
    commitment = build_commitment(
        make_recommendation(), authority, "2026-11-15"
    )
    assert "policy:storage_commit_v1" in commitment
    assert "2026-11-15" in commitment
    assert " o " not in commitment


# ---------------------------------------------------------------------------
# Deterministic dedup over identical inputs.
# ---------------------------------------------------------------------------
def test_commit_is_deterministic_dedup():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation()
    confidence = make_confidence()
    authority = make_authority(policy)
    first = commit(recommendation, confidence, policy, authority)
    second = commit(recommendation, confidence, policy, authority)
    assert first is not None and second is not None
    assert first.commitment == second.commitment
    assert first.expected_outcomes == second.expected_outcomes
    assert (
        build_decision(first).id == build_decision(second).id
    )  # same content-addressed id


# ---------------------------------------------------------------------------
# Traceability binding (unit level; full chain is the integration test).
# ---------------------------------------------------------------------------
def test_commit_binds_recommendation_and_confidence():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation()
    confidence = make_confidence()
    create = commit(recommendation, confidence, policy, make_authority(policy))
    assert create is not None
    assert create.recommendation_id == recommendation.id
    assert create.confidence_id == confidence.id
    assert create.tenant_id == recommendation.tenant_id


def test_commit_rejects_confidence_not_bound_to_recommendation():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation()
    confidence = make_confidence(id=uuid.uuid4(), confidence_score=0.8)
    with pytest.raises(ValueError):
        commit_eligibility(recommendation, confidence, policy, make_authority(policy))


def test_commit_rejects_tenant_mismatch():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation()
    confidence = make_confidence(tenant_id=uuid.uuid4(), confidence_score=0.8)
    with pytest.raises(ValueError):
        commit_eligibility(recommendation, confidence, policy, make_authority(policy))


# ---------------------------------------------------------------------------
# Risk tolerance resolution and eligibility guards.
# ---------------------------------------------------------------------------
def test_resolve_risk_tolerance_maps_score_to_level():
    storage = POLICY_BY_DOMAIN["storage"]
    assert resolve_risk_tolerance(0.5, storage) is None  # below commit
    assert resolve_risk_tolerance(0.75, storage) == RISK_MEDIUM
    assert resolve_risk_tolerance(0.9, storage) == RISK_HIGH
    compute = POLICY_BY_DOMAIN["compute"]
    # compute excludes high: high confidence steps down to the allowed medium.
    assert resolve_risk_tolerance(0.95, compute) == RISK_MEDIUM
    assert resolve_risk_tolerance(0.8, compute) == RISK_MEDIUM
    assert resolve_risk_tolerance(0.7, compute) is None


def test_risk_not_allowed_blocks_commit():
    policy = POLICY_BY_DOMAIN["compute"]
    recommendation = make_recommendation(domain="compute", confidence_score=0.95)
    confidence = make_confidence(confidence_score=0.95)
    authority = make_authority(policy, risk_tolerance=RISK_HIGH)
    assert commit_eligibility(recommendation, confidence, policy, authority) == RISK_NOT_ALLOWED
    assert commit(recommendation, confidence, policy, authority) is None


def test_irreversible_high_risk_requires_threshold():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation(confidence_score=0.8)
    confidence = make_confidence(confidence_score=0.8)
    authority = make_authority(policy, risk_tolerance=RISK_HIGH)
    assert commit_eligibility(recommendation, confidence, policy, authority) == RISK_NOT_ALLOWED


def test_no_authority_blocks_commit_when_required():
    policy = POLICY_BY_DOMAIN["storage"]
    recommendation = make_recommendation()
    confidence = make_confidence()
    assert commit_eligibility(recommendation, confidence, policy, None) == NO_AUTHORITY
    assert commit(recommendation, confidence, policy, None) is None


def test_no_policy_blocks_commit():
    recommendation = make_recommendation()
    confidence = make_confidence()
    authority = make_authority(POLICY_BY_DOMAIN["storage"])
    assert commit_eligibility(recommendation, confidence, None, authority) == NO_POLICY
    assert commit(recommendation, confidence, None, authority) is None


def test_recommendation_domain_resolved_from_alternatives():
    recommendation = make_recommendation(domain="backup")
    assert recommendation_domain(recommendation) == "backup"
    bare = make_recommendation(alternatives_considered=[])
    assert recommendation_domain(bare) is None


def test_policy_authority_id_is_deterministic():
    first = policy_authority_id("storage_commit_v1")
    second = policy_authority_id("storage_commit_v1")
    assert first == second
    assert first != policy_authority_id("compute_commit_v1")