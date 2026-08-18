"""Unit tests for the Recommendation model and deterministic id (Action - Propose)."""
import uuid
from datetime import UTC, datetime

import pytest
from libs.action.recommendation import (
    RECOMMENDATION_NAMESPACE,
    RECOMMENDATION_STATUSES,
    STATUS_ACCEPTED,
    STATUS_PROPOSED,
    RecommendationCreate,
    build_recommendation,
    recommendation_id,
)

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
HYPOTHESIS = uuid.UUID("22222222-2222-2222-2222-222222222222")
CONFIDENCE = uuid.UUID("33333333-3333-3333-3333-333333333333")
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def make_create(**overrides) -> RecommendationCreate:
    base = {
        "tenant_id": TENANT,
        "hypothesis_id": HYPOTHESIS,
        "insight_id": None,
        "confidence_id": CONFIDENCE,
        "action_description": "Expandir el volumen objetivo del almacenamiento.",
        "rationale": "Derivada de la hipótesis y su confidence calibrada.",
        "expected_consequences": [
            "El espacio libre permanecerá por encima del umbral durante 90 días."
        ],
        "alternatives_considered": [
            {
                "action": "compress",
                "rationale": "Menor coste inmediato.",
                "rejected_reason": "Puede no acompañar el ritmo de crecimiento.",
                "confidence": 0.82,
            }
        ],
        "confidence_score": 0.82,
        "status": STATUS_PROPOSED,
        "proposed_at": NOW,
    }
    base.update(overrides)
    return RecommendationCreate(**base)


def test_recommendation_id_is_deterministic_and_content_addressed():
    first = recommendation_id(TENANT, HYPOTHESIS, CONFIDENCE, "action A")
    second = recommendation_id(TENANT, HYPOTHESIS, CONFIDENCE, "action A")
    assert first == second
    # Proposed_at is not part of the id -> re-formulation is idempotent.
    assert first != recommendation_id(TENANT, HYPOTHESIS, CONFIDENCE, "action B")
    assert first != recommendation_id(TENANT, HYPOTHESIS, uuid.uuid4(), "action A")
    assert first != recommendation_id(TENANT, uuid.uuid4(), CONFIDENCE, "action A")
    assert first != recommendation_id(uuid.uuid4(), HYPOTHESIS, CONFIDENCE, "action A")


def test_recommendation_id_namespace_is_documented():
    derived = recommendation_id(TENANT, HYPOTHESIS, CONFIDENCE, "action A")
    assert derived.version == 5
    # The namespace anchors the deterministic derivation (auditable).
    assert RECOMMENDATION_NAMESPACE is not None
    namespace_value = str(RECOMMENDATION_NAMESPACE)
    assert namespace_value.endswith("081")


def test_recommendation_and_create_are_frozen():
    with pytest.raises(ValueError):
        make_create().insight_id = HYPOTHESIS
    recommendation = build_recommendation(make_create())
    with pytest.raises(ValueError):
        recommendation.status = STATUS_ACCEPTED


def test_build_recommendation_mirrors_create_and_assigns_deterministic_id():
    create = make_create()
    recommendation = build_recommendation(create)
    assert recommendation.id == recommendation_id(
        create.tenant_id,
        create.hypothesis_id,
        create.confidence_id,
        create.action_description,
    )
    assert recommendation.tenant_id == TENANT
    assert recommendation.hypothesis_id == HYPOTHESIS
    assert recommendation.confidence_id == CONFIDENCE
    assert recommendation.insight_id is None  # Insight is a future sprint.
    assert recommendation.action_description == create.action_description
    assert recommendation.rationale == create.rationale
    assert recommendation.expected_consequences == create.expected_consequences
    assert recommendation.alternatives_considered == create.alternatives_considered
    assert recommendation.confidence_score == 0.82
    assert recommendation.status == STATUS_PROPOSED
    assert recommendation.proposed_at == NOW


def test_status_lifecycle_set():
    assert STATUS_PROPOSED == "proposed"
    assert RECOMMENDATION_STATUSES == {
        "proposed",
        "accepted",
        "rejected",
        "superseded",
    }


def test_confidence_score_must_be_in_unit_interval():
    with pytest.raises(ValueError):
        make_create(confidence_score=1.5)
    with pytest.raises(ValueError):
        make_create(confidence_score=-0.1)


def test_default_status_and_proposed_at():
    create = make_create()
    assert create.status == STATUS_PROPOSED
    assert create.proposed_at is not None
    recommendation = build_recommendation(create)
    assert recommendation.status == STATUS_PROPOSED