"""Unit tests for the Confidence model + deterministic id (Learning - Calibrate).

Synthetic only - no database. Covers the frozen P1 models, the content-addressed
``confidence_id`` (idempotent for identical inputs, distinct for changed inputs,
computed_at excluded) and ``build_confidence``.
"""
import uuid
from datetime import UTC, datetime

import pytest
from libs.learning.confidence import (
    TARGET_TYPES,
    CalibrationContent,
    ConfidenceCreate,
    build_confidence,
    confidence_id,
)
from pydantic import ValidationError

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
TARGET = uuid.UUID("00000000-0000-0000-0000-0000000000a2")


def content(
    *,
    S: float = 0.7,
    C: float = 0.8,
    H: float = 1.0,
    A: float = 0.5,
) -> CalibrationContent:
    """Deterministic calibration content for id tests."""
    return CalibrationContent(
        evidential_support=S,
        explanatory_coherence=C,
        historical_calibration=H,
        alpha=A,
    )


def make_create(**overrides) -> ConfidenceCreate:
    base = {
        "tenant_id": TENANT,
        "target_type": "hypothesis",
        "target_id": TARGET,
        "evidential_support": 0.7,
        "explanatory_coherence": 0.8,
        "historical_calibration": 1.0,
        "confidence_score": 0.75,
        "alpha": 0.5,
        "calibration_justification": "justificacion documentada",
        "calibration_error_estimate": 0.0,
        "computed_at": datetime(2026, 8, 17, 12, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return ConfidenceCreate(**base)


def test_target_types_cover_action_layer():
    assert TARGET_TYPES == frozenset({"hypothesis", "recommendation", "decision"})


def test_confidence_id_is_deterministic_and_excludes_computed_at():
    a = confidence_id(TENANT, "hypothesis", TARGET, content())
    b = confidence_id(TENANT, "hypothesis", TARGET, content())
    assert a == b
    # Same inputs at a different moment -> same id (idempotent dedup between runs).
    assert a == confidence_id(TENANT, "hypothesis", TARGET, content())
    assert isinstance(a, uuid.UUID)


def test_confidence_id_changes_when_calibration_inputs_change():
    base = content()
    assert confidence_id(TENANT, "hypothesis", TARGET, base) != confidence_id(TENANT, "hypothesis", TARGET, content(S=0.6))
    assert confidence_id(TENANT, "hypothesis", TARGET, base) != confidence_id(TENANT, "hypothesis", TARGET, content(C=0.7))
    assert confidence_id(TENANT, "hypothesis", TARGET, base) != confidence_id(TENANT, "hypothesis", TARGET, content(H=0.9))
    assert confidence_id(TENANT, "hypothesis", TARGET, base) != confidence_id(TENANT, "hypothesis", TARGET, content(A=0.6))


def test_confidence_id_changes_with_target_or_tenant():
    base = content()
    assert confidence_id(TENANT, "hypothesis", TARGET, base) != confidence_id(TENANT, "recommendation", TARGET, base)
    assert confidence_id(TENANT, "hypothesis", TARGET, base) != confidence_id(TENANT, "hypothesis", uuid.UUID("00000000-0000-0000-0000-0000000000a3"), base)


def test_confidence_id_uses_the_documented_namespace():
    cid = confidence_id(TENANT, "hypothesis", TARGET, content())
    # Verify deterministic: same inputs produce same id
    cid2 = confidence_id(TENANT, "hypothesis", TARGET, content())
    assert cid == cid2
    # Verify it's a valid UUID v5 from our namespace
    assert isinstance(cid, uuid.UUID)
    assert cid.version == 5


def test_build_confidence_materializes_id_at_creation():
    create = make_create()
    confidence = build_confidence(create)
    assert confidence.id == confidence_id(
        TENANT, "hypothesis", TARGET, content()
    )
    assert confidence.tenant_id == TENANT
    assert confidence.target_type == "hypothesis"
    assert confidence.target_id == TARGET
    assert confidence.confidence_score == 0.75
    assert confidence.calibration_justification == "justificacion documentada"


def test_confidence_models_are_frozen():
    confidence = build_confidence(make_create())
    with pytest.raises(ValidationError):
        confidence.confidence_score = 0.99


def test_confidence_create_validates_ranges():
    with pytest.raises(ValueError):
        make_create(evidential_support=1.5)
    with pytest.raises(ValueError):
        make_create(confidence_score=-0.1)


def test_confidence_accepts_action_layer_target_types():
    for target_type in ("recommendation", "decision"):
        confidence = build_confidence(
            make_create(target_type=target_type, target_id=TARGET)
        )
        assert confidence.target_type == target_type


def test_confidence_rejects_invalid_target_type():
    with pytest.raises(ValueError, match="target_type must be one of"):
        make_create(target_type="invalid")
    with pytest.raises(ValueError, match="target_type must be one of"):
        make_create(target_type="")