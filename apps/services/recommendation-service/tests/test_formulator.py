"""Unit tests for the Recommendation Formulator (Action/Propose, pure functions)."""
import uuid
from datetime import UTC, datetime

import pytest
from libs.action.recommendation import STATUS_PROPOSED, build_recommendation
from libs.learning.confidence import Confidence
from libs.perception.context import Context
from libs.procedural_memory.action_space import ACTION_SPACE_LIBRARY
from libs.reasoning.hypothesis import Hypothesis

from src.formulator import (
    formulate,
    resolve_active_context,
    resolve_domain,
    select_action_space,
)

TENANT = uuid.uuid4()
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def make_hypothesis(description="Hipótesis candidata de saturación de disco.") -> Hypothesis:
    return Hypothesis(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        anomaly_ids=[uuid.uuid4()],
        pattern_ids=[uuid.uuid4()],
        description=description,
        predicted_consequences=["El volumen de datos persistido seguirá creciendo."],
        falsification_criterion="Si el volumen deja de crecer, la hipótesis queda descartada.",
        coherence_score=0.5,
        status="candidate",
        generated_at=NOW,
    )


def make_confidence(hypothesis: Hypothesis) -> Confidence:
    return Confidence(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        target_type="hypothesis",
        target_id=hypothesis.id,
        evidential_support=0.7,
        explanatory_coherence=0.8,
        historical_calibration=1.0,
        confidence_score=0.82,
        alpha=0.5,
        calibration_justification="S=0.7000, C=0.8000, ECE=0.0000, C_final=0.7500.",
        calibration_error_estimate=0.0,
        computed_at=NOW,
    )


def make_context(
    mental_model_id="resource_pressure",
    purpose="infrastructure_health",
    ctx_id=None,
) -> Context:
    return Context(
        id=ctx_id or uuid.uuid4(),
        tenant_id=TENANT,
        evidence_ids=[uuid.uuid4()],
        mental_model_id=mental_model_id,
        purpose=purpose,
        coherence_score=0.7,
        competing_models=[],
        activated_at=NOW,
        is_active=True,
    )


def space_for(domain: str, purpose: str):
    return select_action_space(ACTION_SPACE_LIBRARY, domain, purpose)


# One representative scope per domain (mental model -> domain -> purpose).
DOMAIN_CASES = [
    ("resource_pressure", "infrastructure_health", "storage"),
    ("capacity_risk", "capacity_management", "backup"),
    ("auth_compromise", "security_posture", "security"),
    ("service_failure", "infrastructure_health", "compute"),
    ("connectivity_degradation", "infrastructure_health", "network"),
]


@pytest.mark.parametrize("model,purpose,domain", DOMAIN_CASES)
def test_formulate_per_domain(model, purpose, domain):
    hypothesis = make_hypothesis()
    confidence = make_confidence(hypothesis)
    context = make_context(mental_model_id=model, purpose=purpose)
    entry = space_for(domain, purpose)
    assert entry is not None
    assert resolve_domain(context) == domain

    create = formulate(hypothesis, confidence, context, entry)
    assert create is not None
    assert create.tenant_id == TENANT
    assert create.hypothesis_id == hypothesis.id
    assert create.confidence_id == confidence.id
    assert create.insight_id is None
    assert create.status == STATUS_PROPOSED
    # The action must belong to the explicit space of the domain.
    action_words = create.action_description.lower()
    assert any(word in action_words for word in ("expandir", "cambiar", "resetear",
                                                 "reiniciar", "modificar"))
    assert create.expected_consequences, "observable expected consequences required"
    assert create.alternatives_considered, "at least one alternative when options exist"
    for alternative in create.alternatives_considered:
        assert alternative["action"] in entry.allowed_actions
        assert alternative["action"] != _leading(create)
        assert alternative["rationale"]
        assert alternative["rejected_reason"]
        assert alternative["confidence"] == round(confidence.confidence_score, 4)


def _leading(create) -> str:
    # The leading action is the one described by the action_description templates.
    for action, text in _descriptions().items():
        if text == create.action_description:
            return action
    return "unknown"


def _descriptions():
    from src.formulator.formulator import ACTION_DESCRIPTION_TEMPLATES

    return ACTION_DESCRIPTION_TEMPLATES


def test_r4_confidence_must_calibrate_the_leading_hypothesis():
    hypothesis = make_hypothesis()
    other = make_hypothesis(description="Otra hipótesis competidora.")
    confidence = make_confidence(other)  # calibrates a DIFFERENT hypothesis
    context = make_context()
    entry = space_for("storage", "infrastructure_health")
    with pytest.raises(ValueError, match="target_id mismatch"):
        formulate(hypothesis, confidence, context, entry)


def test_r4_confidence_target_type_must_be_hypothesis():
    hypothesis = make_hypothesis()
    confidence = make_confidence(hypothesis).model_copy(
        update={"target_type": "recommendation"}
    )
    context = make_context()
    entry = space_for("storage", "infrastructure_health")
    with pytest.raises(ValueError, match="target_type"):
        formulate(hypothesis, confidence, context, entry)


def test_r4_tenant_consistency():
    hypothesis = make_hypothesis()
    confidence = make_confidence(hypothesis)
    context = make_context().model_copy(update={"tenant_id": uuid.uuid4()})
    entry = space_for("storage", "infrastructure_health")
    with pytest.raises(ValueError, match="tenant mismatch"):
        formulate(hypothesis, confidence, context, entry)


def test_p6_advisory_only_no_side_effects():
    hypothesis = make_hypothesis()
    confidence = make_confidence(hypothesis)
    context = make_context()
    entry = space_for("storage", "infrastructure_health")
    create = formulate(hypothesis, confidence, context, entry)
    assert create.status == STATUS_PROPOSED
    assert create.insight_id is None
    # Pure: the only output is the RecommendationCreate (never executed, no I/O).
    recommendation = build_recommendation(create)
    assert recommendation.status == STATUS_PROPOSED


def test_anti_order_no_unqualified_imperative_language():
    hypothesis = make_hypothesis()
    confidence = make_confidence(hypothesis)
    for model, purpose, domain in DOMAIN_CASES:
        context = make_context(mental_model_id=model, purpose=purpose)
        entry = space_for(domain, purpose)
        create = formulate(hypothesis, confidence, context, entry)
        text = (create.action_description + " " + create.rationale).lower()
        for forbidden in ("run now", "ejecutar ahora", "hazlo ahora", "ejecute ahora"):
            assert forbidden not in text


def test_rationale_is_traceable_to_hypothesis_and_confidence():
    hypothesis = make_hypothesis()
    confidence = make_confidence(hypothesis)
    context = make_context()
    entry = space_for("storage", "infrastructure_health")
    create = formulate(hypothesis, confidence, context, entry)
    rationale = create.rationale
    assert str(hypothesis.id) in rationale
    assert hypothesis.description[:40] in rationale
    assert str(confidence.id) in rationale
    assert "0.8200" in rationale  # the calibrated score is cited
    assert context.mental_model_id in rationale
    assert context.purpose in rationale
    assert entry.action_id in rationale
    # No unbacked causal claims beyond the declared facts.
    assert "causó" not in rationale.lower()


def test_confidence_score_is_the_calibrated_hypothesis_score():
    hypothesis = make_hypothesis()
    confidence = make_confidence(hypothesis)
    context = make_context()
    entry = space_for("storage", "infrastructure_health")
    create = formulate(hypothesis, confidence, context, entry)
    assert create.confidence_score == confidence.confidence_score
    assert create.confidence_score != hypothesis.coherence_score


def test_formulate_is_deterministic():
    hypothesis = make_hypothesis()
    confidence = make_confidence(hypothesis)
    context = make_context()
    entry = space_for("storage", "infrastructure_health")
    first = formulate(hypothesis, confidence, context, entry)
    second = formulate(hypothesis, confidence, context, entry)
    assert first.action_description == second.action_description
    assert first.rationale == second.rationale
    assert first.expected_consequences == second.expected_consequences
    assert first.alternatives_considered == second.alternatives_considered
    assert build_recommendation(first).id == build_recommendation(second).id


def test_formulate_returns_none_outside_explicit_space():
    hypothesis = make_hypothesis()
    confidence = make_confidence(hypothesis)
    context = make_context()  # storage domain
    security_entry = space_for("security", "security_posture")
    assert formulate(hypothesis, confidence, context, security_entry) is None


def test_resolve_domain_mappings_and_fallback():
    assert resolve_domain(make_context("resource_pressure", "infrastructure_health")) == "storage"
    assert resolve_domain(make_context("capacity_risk", "capacity_management")) == "backup"
    assert resolve_domain(make_context("auth_compromise", "security_posture")) == "security"
    # Fallback by purpose when the mental model is unmapped.
    unknown = make_context(mental_model_id="unmapped_model", purpose="security_posture")
    assert resolve_domain(unknown) == "security"
    # Unmapped model AND unmapped purpose -> no explicit space -> None.
    assert resolve_domain(make_context("unmapped_model", "some_purpose")) is None


def test_select_action_space_respects_domain_and_purpose():
    storage = space_for("storage", "capacity_management")
    assert storage is not None and storage.domain == "storage"
    # Security space does not apply to capacity management.
    assert select_action_space(ACTION_SPACE_LIBRARY, "security", "capacity_management") is None
    assert select_action_space(ACTION_SPACE_LIBRARY, None, "security_posture") is None


def test_resolve_active_context_follows_hypothesis_chain():
    hypothesis = make_hypothesis()
    active = make_context(ctx_id=uuid.uuid4())
    inactive = make_context(ctx_id=uuid.uuid4()).model_copy(update={"is_active": False})
    anomaly = type("Anomaly", (), {"id": hypothesis.anomaly_ids[0], "context_id": active.id})()
    assert resolve_active_context(hypothesis, [anomaly], [inactive, active]) == active
    # No active activation -> None (no recommendation without an Active Context).
    assert resolve_active_context(hypothesis, [anomaly], [inactive]) is None