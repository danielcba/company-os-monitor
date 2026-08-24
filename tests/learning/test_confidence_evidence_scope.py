"""Phase 7 — Confidence Evidence Scope tests.

A Hypothesis's Confidence must be calibratable exclusively from evidence
within its cognitive scope. Evidence from another hypothesis must NOT
affect Confidence(A).

These tests are OBLIGATORY per §11 of the remediation prompt.
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from libs.learning.confidence import (
    CalibrationContent,
    ConfidenceCreate,
    EvidenceScopeError,
    build_confidence,
    confidence_id,
    validate_confidence_evidence_scope,
)


def _make_tenant() -> uuid.UUID:
    return uuid.uuid4()


def _make_evidence_ids(n: int = 3) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(n)]


# ---------------------------------------------------------------------------
# ID deterministic tests
# ---------------------------------------------------------------------------

def test_same_content_same_id():
    """Phase 7: same inputs → same id."""
    tenant = _make_tenant()
    evidence = _make_evidence_ids(2)
    content = CalibrationContent(
        evidential_support=0.75,
        explanatory_coherence=0.80,
        historical_calibration=0.65,
        alpha=0.5,
        evidence_ids=evidence,
    )
    id1 = confidence_id(tenant, "hypothesis", uuid.uuid4(), content)
    id2 = confidence_id(tenant, "hypothesis", uuid.uuid4(), content)
    # Different target_id → different id.
    assert id1 != id2

    # Same target_id → same id.
    target = uuid.uuid4()
    id3 = confidence_id(tenant, "hypothesis", target, content)
    id4 = confidence_id(tenant, "hypothesis", target, content)
    assert id3 == id4


def test_different_evidence_different_id():
    """Phase 7: different evidence → different id."""
    tenant = _make_tenant()
    target = uuid.uuid4()
    evidence_a = [uuid.uuid4(), uuid.uuid4()]
    evidence_b = [uuid.uuid4(), uuid.uuid4()]
    content_a = CalibrationContent(
        evidential_support=0.75,
        explanatory_coherence=0.80,
        historical_calibration=0.65,
        alpha=0.5,
        evidence_ids=evidence_a,
    )
    content_b = CalibrationContent(
        evidential_support=0.75,
        explanatory_coherence=0.80,
        historical_calibration=0.65,
        alpha=0.5,
        evidence_ids=evidence_b,
    )
    id_a = confidence_id(tenant, "hypothesis", target, content_a)
    id_b = confidence_id(tenant, "hypothesis", target, content_b)
    assert id_a != id_b


def test_reordered_evidence_same_id():
    """Phase 7: reordered evidence → same id (evidence is sorted in hash)."""
    tenant = _make_tenant()
    target = uuid.uuid4()
    evidence = _make_evidence_ids(3)
    content_a = CalibrationContent(
        evidential_support=0.75,
        explanatory_coherence=0.80,
        historical_calibration=0.65,
        alpha=0.5,
        evidence_ids=evidence,
    )
    content_b = CalibrationContent(
        evidential_support=0.75,
        explanatory_coherence=0.80,
        historical_calibration=0.65,
        alpha=0.5,
        evidence_ids=list(reversed(evidence)),
    )
    id_a = confidence_id(tenant, "hypothesis", target, content_a)
    id_b = confidence_id(tenant, "hypothesis", target, content_b)
    assert id_a == id_b


# ---------------------------------------------------------------------------
# Evidence scope validation tests (OBLIGATORY per §11)
# ---------------------------------------------------------------------------

def test_confidence_with_scoped_evidence_passes():
    """Phase 7: Hypothesis A evidence [A1, A2] → calibration using A1, A2 is valid."""
    evidence_a = _make_evidence_ids(2)
    validate_confidence_evidence_scope(
        confidence_evidence_ids=evidence_a,
        hypothesis_evidence_ids=evidence_a,
    )


def test_confidence_with_subset_of_scope_passes():
    """Phase 7: using a subset of scope evidence is valid (some may be irrelevant)."""
    scope = _make_evidence_ids(4)
    validate_confidence_evidence_scope(
        confidence_evidence_ids=scope[:2],
        hypothesis_evidence_ids=scope,
    )


def test_confidence_with_evidence_from_another_hypothesis_fails():
    """Phase 7: Hypothesis A confidence must NOT use B's evidence.

    Hypothesis A evidence: A1, A2
    Hypothesis B evidence: B1, B2

    Calibrating A with B1 must FAIL.
    """
    evidence_a = _make_evidence_ids(2)
    evidence_b = _make_evidence_ids(2)
    mixed_evidence = [evidence_a[0], evidence_b[0]]  # A1 + B1

    with pytest.raises(EvidenceScopeError, match="outside the hypothesis scope"):
        validate_confidence_evidence_scope(
            confidence_evidence_ids=mixed_evidence,
            hypothesis_evidence_ids=evidence_a,
        )


def test_empty_evidence_passes():
    """Phase 7: empty evidence list is always valid."""
    validate_confidence_evidence_scope(
        confidence_evidence_ids=[],
        hypothesis_evidence_ids=[uuid.uuid4()],
    )


def test_same_organization_type_different_hypothesis_no_effect():
    """Phase 7: same organization_type in another Hypothesis does NOT alter Confidence(A).

    Hypothesis A uses evidence E1, E2 (organization_type: resource_exhaustion).
    Hypothesis B uses evidence E3, E4 (also resource_exhaustion).
    Confidence(A) must only use E1, E2 — E3, E4 are out of scope.
    """
    evidence_a = _make_evidence_ids(2)  # E1, E2
    evidence_b = _make_evidence_ids(2)  # E3, E4

    # Adding B3 (from Hypothesis B) to A's calibration must fail.
    with pytest.raises(EvidenceScopeError):
        validate_confidence_evidence_scope(
            confidence_evidence_ids=[evidence_a[0], evidence_b[0]],
            hypothesis_evidence_ids=evidence_a,
        )

    # Confidence(A) with only E1, E2 is valid.
    validate_confidence_evidence_scope(
        confidence_evidence_ids=evidence_a,
        hypothesis_evidence_ids=evidence_a,
    )


def test_build_confidence_includes_evidence_ids():
    """Phase 7: build_confidence propagates evidence_ids to the model."""
    evidence = _make_evidence_ids(3)
    create = ConfidenceCreate(
        tenant_id=_make_tenant(),
        target_type="hypothesis",
        target_id=uuid.uuid4(),
        evidential_support=0.75,
        explanatory_coherence=0.80,
        historical_calibration=0.65,
        confidence_score=0.72,
        alpha=0.5,
        calibration_justification="Strong evidential support from scoped observations",
        calibration_error_estimate=0.08,
        evidence_ids=evidence,
    )
    conf = build_confidence(create)
    assert conf.evidence_ids == evidence
