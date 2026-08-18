"""Unit tests for the Hypothesis Generator (Reasoning/Predict).

Synthetic Context/Pattern/Anomaly objects only - no database. Covers: template
instantiation per scope with measured-fact placeholders, multiple competing
hypotheses (>=2, distinct ids - no premature convergence), the anti-conclusion
constraint (tentative/hypothetical language, no asserted causation), the
mandatory falsification criterion on EVERY hypothesis, and the deterministic
idempotent hypothesis id.
"""
import uuid
from datetime import UTC, datetime

import pytest
from libs.perception.context import Context
from libs.procedural_memory.hypothesis_templates import (
    HYPOTHESIS_TEMPLATE_LIBRARY,
)
from libs.reasoning.anomaly import ANOMALY_CLASS_POINT, Anomaly
from libs.reasoning.pattern import Pattern

from src.generator import generate

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Words that would assert causation as fact or reach conclusions (the framework
# pairs explanation with prediction; asserting "es la causa" is an assumption,
# not a hypothesis; premature convergence is a cognitive failure).
BANNED_HYPOTHESIS_LANGUAGE = (
    "es la causa",
    "está confirmado",
    "es seguro que",
    "la razón es",
    "porque definitivamente",
)


def make_context(model_id: str, purpose: str, ctx_id: uuid.UUID | None = None) -> Context:
    return Context(
        id=ctx_id or uuid.uuid4(),
        tenant_id=TENANT,
        evidence_ids=[uuid.uuid4()],
        mental_model_id=model_id,
        purpose=purpose,
        coherence_score=0.7,
        competing_models=[],
        activated_at=datetime(2026, 8, 17, 12, 0, tzinfo=UTC),
    )


def make_pattern(model_id: str, ctx_id: uuid.UUID, pattern_id: uuid.UUID | None = None) -> Pattern:
    return Pattern(
        id=pattern_id or uuid.uuid4(),
        tenant_id=TENANT,
        context_id=ctx_id,
        pattern_type="temporal",
        description="Regularidad detectada en el scope.",
        strength_measure=0.9,
        frequency="daily",
        detected_at=datetime(2026, 8, 17, 11, 0, tzinfo=UTC),
        is_active=True,
    )


def make_anomaly(
    model_id: str,
    purpose: str,
    ctx_id: uuid.UUID | None = None,
    pattern_id: uuid.UUID | None = None,
) -> Anomaly:
    return Anomaly(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        context_id=ctx_id or uuid.uuid4(),
        pattern_id=pattern_id or uuid.uuid4(),
        deviation_score=2.5,
        tolerance_threshold=1.0,
        anomaly_class=ANOMALY_CLASS_POINT,
        detected_at=datetime(2026, 8, 17, 12, 30, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    "scope",
    [
        ("resource_pressure", "infrastructure_health"),
        ("capacity_risk", "infrastructure_health"),
        ("auth_compromise", "security_posture"),
    ],
)
def test_each_template_scope_generates_competing_hypotheses(scope):
    model_id, purpose = scope
    ctx_id = uuid.uuid4()
    pattern_id = uuid.uuid4()
    anomaly = make_anomaly(model_id, purpose, ctx_id, pattern_id)
    creations = generate(
        anomaly,
        [make_context(model_id, purpose, ctx_id)],
        [make_pattern(model_id, ctx_id, pattern_id)],
        library=HYPOTHESIS_TEMPLATE_LIBRARY,
    )
    assert len(creations) >= 2, "premature convergence: must emit >=2 competing hypotheses"
    for create in creations:
        assert create.predicted_consequences, "every hypothesis needs observable consequences"
        assert create.falsification_criterion.strip(), "falsification is mandatory"
        assert create.status == "candidate"
        assert model_id in create.description
        assert f"{anomaly.deviation_score:.1f}" in create.description


def test_competing_hypotheses_have_distinct_ids():
    ctx_id = uuid.uuid4()
    anomaly = make_anomaly("resource_pressure", "infrastructure_health", ctx_id)
    creations = generate(
        anomaly,
        [make_context("resource_pressure", "infrastructure_health", ctx_id)],
        [],
        library=HYPOTHESIS_TEMPLATE_LIBRARY,
    )
    assert len(creations) >= 2
    descriptions = {create.description for create in creations}
    assert len(descriptions) == len(creations), "distinct explanations must be distinct hypotheses"


def test_hypotheses_are_tentative_never_asserted_cause():
    ctx_id = uuid.uuid4()
    anomaly = make_anomaly("resource_pressure", "infrastructure_health", ctx_id)
    creations = generate(
        anomaly,
        [make_context("resource_pressure", "infrastructure_health", ctx_id)],
        [],
        library=HYPOTHESIS_TEMPLATE_LIBRARY,
    )
    for create in creations:
        lowered = create.description.lower()
        for banned in BANNED_HYPOTHESIS_LANGUAGE:
            assert banned not in lowered
        assert any(word in lowered for word in ("podría", "candidata", "explicar", "podria"))


def test_unresolved_scope_yields_no_hypotheses():
    anomaly = make_anomaly("resource_pressure", "infrastructure_health", uuid.uuid4())
    creations = generate(anomaly, [], [], library=HYPOTHESIS_TEMPLATE_LIBRARY)
    assert creations == []


def test_unmatched_scope_yields_no_hypotheses():
    ctx_id = uuid.uuid4()
    anomaly = make_anomaly("service_failure", "security_posture", ctx_id)
    creations = generate(
        anomaly,
        [make_context("service_failure", "security_posture", ctx_id)],
        [],
        library=HYPOTHESIS_TEMPLATE_LIBRARY,
    )
    assert creations == []


def test_generation_is_deterministic_and_idempotent():
    ctx_id = uuid.uuid4()
    anomaly = make_anomaly("capacity_risk", "infrastructure_health", ctx_id)
    inputs = [
        [make_context("capacity_risk", "infrastructure_health", ctx_id)],
        [],
        HYPOTHESIS_TEMPLATE_LIBRARY,
    ]
    first = generate(anomaly, *inputs)
    second = generate(anomaly, *inputs)
    assert [c.description for c in first] == [c.description for c in second]
    from libs.reasoning.hypothesis import build_hypothesis

    assert [build_hypothesis(c).id for c in first] == [build_hypothesis(c).id for c in second]


def test_hypothesis_id_differs_per_explanation_same_anomaly():
    from libs.reasoning.hypothesis import hypothesis_id

    anomaly_id = uuid.uuid4()
    base = {
        "tenant_id": TENANT,
        "anomaly_ids": [anomaly_id],
        "pattern_ids": [],
    }
    h1 = hypothesis_id(TENANT, base["anomaly_ids"], base["pattern_ids"], "explicación A")
    h2 = hypothesis_id(TENANT, base["anomaly_ids"], base["pattern_ids"], "explicación B")
    assert h1 != h2, "competing explanations must have distinct ids"


def test_frequency_placeholder_uses_measured_pattern_when_present():
    ctx_id = uuid.uuid4()
    pattern_id = uuid.uuid4()
    anomaly = make_anomaly("resource_pressure", "infrastructure_health", ctx_id, pattern_id)
    creations = generate(
        anomaly,
        [make_context("resource_pressure", "infrastructure_health", ctx_id)],
        [make_pattern("resource_pressure", ctx_id, pattern_id)],
        library=HYPOTHESIS_TEMPLATE_LIBRARY,
    )
    assert creations
    assert any("daily" in c for c in creations[0].predicted_consequences)