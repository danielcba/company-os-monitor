"""Unit tests for the Decision model (Action - Commit).

Covers the deterministic content-addressed ``decision_id`` (idempotent dedup,
P1), the frozen P1 model, the build espejo and the declared lifecycle defaults.
No I/O: pure model tests.
"""
import uuid
from datetime import UTC, datetime

import pytest
from libs.action.decision import (
    DECISION_NAMESPACE,
    STATUS_COMMITTED,
    DecisionCreate,
    build_decision,
    decision_id,
)
from pydantic import ValidationError

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
RECOMMENDATION = uuid.UUID("11111111-1111-1111-1111-111111111111")
CONFIDENCE = uuid.UUID("22222222-2222-2222-2222-222222222222")
AUTHORITY = uuid.UUID("33333333-3333-3333-3333-333333333333")
COMMITTED_AT = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def make_create(**overrides) -> DecisionCreate:
    base = {
        "tenant_id": TENANT,
        "recommendation_id": RECOMMENDATION,
        "confidence_id": CONFIDENCE,
        "authority_id": AUTHORITY,
        "commitment": (
            "Expandir el volumen objetivo del almacenamiento antes del umbral "
            "proyectado. Compromiso registrado bajo la autoridad policy:storage_commit_v1."
        ),
        "expected_outcomes": [
            {
                "prediction": "El espacio libre permanecerá por encima del umbral.",
                "verifiable_by": "disk_free_percent",
                "deadline": "2026-11-15",
            }
        ],
        "risk_tolerance": "medium",
        "status": STATUS_COMMITTED,
        "committed_at": COMMITTED_AT,
    }
    base.update(overrides)
    return DecisionCreate(**base)


def test_decision_id_is_deterministic_and_content_addressed():
    first = decision_id(TENANT, RECOMMENDATION, CONFIDENCE)
    second = decision_id(TENANT, RECOMMENDATION, CONFIDENCE)
    assert first == second
    assert first.version == 5
    assert first == uuid.uuid5(
        DECISION_NAMESPACE, f"{TENANT}:{RECOMMENDATION}:{CONFIDENCE}"
    )


def test_decision_id_changes_with_tenant_recommendation_confidence():
    base = decision_id(TENANT, RECOMMENDATION, CONFIDENCE)
    assert decision_id(uuid.uuid4(), RECOMMENDATION, CONFIDENCE) != base
    assert decision_id(TENANT, uuid.uuid4(), CONFIDENCE) != base
    assert decision_id(TENANT, RECOMMENDATION, uuid.uuid4()) != base


def test_decision_id_excludes_committed_at():
    """committed_at is deliberately excluded: re-committing over the same
    inputs produces the same id (idempotent dedup by primary key, P1)."""
    d1 = decision_id(TENANT, RECOMMENDATION, CONFIDENCE)
    d2 = decision_id(TENANT, RECOMMENDATION, CONFIDENCE)
    assert d1 == d2


def test_decision_models_are_frozen():
    with pytest.raises(ValidationError):
        make_create().commitment = "otra"  # type: ignore[misc]
    decision = build_decision(make_create())
    with pytest.raises(ValidationError):
        decision.commitment = "otra"  # type: ignore[misc]


def test_decision_create_defaults():
    create = make_create(
        risk_tolerance="low",
        status=STATUS_COMMITTED,
    )
    assert create.status == STATUS_COMMITTED
    assert create.risk_tolerance == "low"
    assert create.executed_at is None
    assert create.actual_outcomes is None


def test_build_decision_mirrors_create_with_deterministic_id():
    create = make_create()
    decision = build_decision(create)
    assert decision.id == decision_id(
        create.tenant_id, create.recommendation_id, create.confidence_id
    )
    assert decision.tenant_id == create.tenant_id
    assert decision.recommendation_id == create.recommendation_id
    assert decision.confidence_id == create.confidence_id
    assert decision.authority_id == create.authority_id
    assert decision.commitment == create.commitment
    assert decision.expected_outcomes == create.expected_outcomes
    assert decision.risk_tolerance == create.risk_tolerance
    assert decision.status == create.status
    assert decision.committed_at == create.committed_at
    assert decision.executed_at == create.executed_at
    assert decision.actual_outcomes == create.actual_outcomes


def test_same_inputs_same_decision_id_different_committed_at():
    """Two runs at different instants over the same inputs share the decision id."""
    d1 = build_decision(make_create(committed_at=COMMITTED_AT))
    d2 = build_decision(make_create(committed_at=COMMITTED_AT.replace(minute=30)))
    assert d1.id == d2.id
    assert d1.committed_at != d2.committed_at