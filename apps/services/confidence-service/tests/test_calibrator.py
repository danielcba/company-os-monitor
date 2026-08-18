"""Unit tests for the Confidence Calibrator (pure functions, no I/O).

Covers: evidential support from Quality Classes with documented +/- signs,
the anti-tuning guarantee (identical inputs -> identical score and id), the
always-present justification documenting alpha/M/L0, first-data behaviour
without history (historical_calibration=1.0) and the real ECE path with
history, plus the scope-evidence resolution chain (hypothesis -> anomaly ->
context -> evidence).
"""
import uuid
from datetime import UTC, datetime

import pytest
from libs.cognitive_core.calibration_model import CalibrationParams
from libs.learning.confidence import build_confidence
from libs.perception.context import Context
from libs.perception.evidence import Evidence
from libs.perception.observation import QualityClass
from libs.reasoning.anomaly import ANOMALY_CLASS_POINT, Anomaly
from libs.reasoning.hypothesis import STATUS_CANDIDATE, Hypothesis

from src.calibrator import (
    calibrate,
    coherence_score,
    evidential_support_score,
    historical_calibration_factor,
    resolve_scope_evidence,
)

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
PARAMS = CalibrationParams()


def make_evidence(
    organization_type: str,
    quality_class: QualityClass,
    evidence_id: uuid.UUID | None = None,
) -> Evidence:
    return Evidence(
        id=evidence_id or uuid.uuid4(),
        tenant_id=TENANT,
        observation_ids=[uuid.uuid4()],
        organization_type=organization_type,
        description=f"evidencia factual de {organization_type}",
        quality_class=quality_class,
        weight=0.5,
        organized_at=NOW,
    )


def make_hypothesis(hypothesis_id: uuid.UUID | None = None) -> Hypothesis:
    return Hypothesis(
        id=hypothesis_id or uuid.uuid4(),
        tenant_id=TENANT,
        anomaly_ids=[uuid.uuid4()],
        pattern_ids=[],
        description="Hipotesis candidata de saturacion de disco.",
        predicted_consequences=["Consecuencia observable."],
        falsification_criterion="Criterio de falsificacion.",
        coherence_score=0.5,
        status=STATUS_CANDIDATE,
        generated_at=NOW,
    )


def test_evidential_support_from_quality_classes_and_signs():
    batch = [
        make_evidence("resource_exhaustion_evidence", QualityClass.Q1),
        make_evidence("service_degradation_evidence", QualityClass.Q2),
        make_evidence("auth_anomaly_evidence", QualityClass.Q4),
    ]
    inputs = {
        "explains": ["resource_exhaustion_evidence", "service_degradation_evidence"],
        "contradicts": [],
    }
    # L = 0.875 + 0.625 = 1.5 -> S = 1/(1+e^-1.5) = 0.81757 (known value).
    S = evidential_support_score(batch, inputs, L0=0.0)
    assert S == pytest.approx(0.817574, abs=1e-5)
    # A contradicted evidence flips its sign: L = 0.875 - 0.625 = 0.25 -> 0.56218.
    flipped = {
        "explains": ["resource_exhaustion_evidence"],
        "contradicts": ["service_degradation_evidence"],
    }
    assert evidential_support_score(batch, flipped, L0=0.0) == pytest.approx(0.562177, abs=1e-5)
    # Neutral evidence (declared in neither) does not contribute to S -> 0.5.
    neutral = {"explains": [], "contradicts": []}
    assert evidential_support_score(batch, neutral, L0=0.0) == 0.5


def test_coherence_score_uses_scope_evidence_and_constraints():
    batch = [
        make_evidence("resource_exhaustion_evidence", QualityClass.Q1),
        make_evidence("service_degradation_evidence", QualityClass.Q2),
        make_evidence("auth_anomaly_evidence", QualityClass.Q4),
    ]
    inputs = {
        "explains": ["resource_exhaustion_evidence", "service_degradation_evidence"],
        "contradicts": [],
    }
    # 2 explained / (2 + 0 + 1 unexplained) = 0.6667.
    assert coherence_score("h", batch, inputs) == pytest.approx(2 / 3)


def test_calibrate_same_inputs_same_score_anti_tuning():
    hypothesis = make_hypothesis()
    batch = [
        make_evidence("resource_exhaustion_evidence", QualityClass.Q1),
        make_evidence("service_degradation_evidence", QualityClass.Q2),
    ]
    inputs = {"explains": ["resource_exhaustion_evidence", "service_degradation_evidence"]}
    first = build_confidence(calibrate(hypothesis, batch, inputs, PARAMS, None))
    second = build_confidence(calibrate(hypothesis, batch, inputs, PARAMS, None))
    # Identical inputs -> identical id, score and justification (the only field
    # that legitimately differs is computed_at, which is outside the content id).
    assert first.id == second.id
    assert first.confidence_score == second.confidence_score
    assert first.calibration_justification == second.calibration_justification
    assert first.evidential_support == second.evidential_support
    assert first.explanatory_coherence == second.explanatory_coherence
    assert first.historical_calibration == second.historical_calibration


def test_calibrate_without_history_is_first_data_documented():
    hypothesis = make_hypothesis()
    batch = [make_evidence("resource_exhaustion_evidence", QualityClass.Q1)]
    inputs = {"explains": ["resource_exhaustion_evidence"]}
    create = calibrate(hypothesis, batch, inputs, PARAMS, None)
    assert create.historical_calibration == 1.0
    assert create.calibration_error_estimate == 0.0
    # C_final = [0.5*S + 0.5*C] * 1.0 with S = 0.70579 (Q1 support), C = 1.0.
    assert create.evidential_support == pytest.approx(0.705785, abs=1e-5)
    assert create.explanatory_coherence == 1.0
    assert create.confidence_score == pytest.approx(0.852892, abs=1e-5)
    assert "sin historial de outcomes" in create.calibration_justification


def test_calibrate_with_history_applies_real_ece():
    hypothesis = make_hypothesis()
    batch = [make_evidence("resource_exhaustion_evidence", QualityClass.Q1)]
    inputs = {"explains": ["resource_exhaustion_evidence"]}
    history = [(0.2, 0), (0.8, 1)]
    create = calibrate(hypothesis, batch, inputs, PARAMS, history)
    # ECE = 0.2 -> historical_calibration = 0.8, error estimate = 0.2.
    assert create.calibration_error_estimate == pytest.approx(0.2, abs=1e-5)
    assert create.historical_calibration == pytest.approx(0.8, abs=1e-5)
    # C_final = 0.852892 * 0.8 = 0.68231 (calibration factor measured from outcomes).
    assert create.confidence_score == pytest.approx(0.682314, abs=1e-5)


def test_calibrate_targets_the_hypothesis_and_carries_tenant():
    hypothesis = make_hypothesis()
    batch = [make_evidence("resource_exhaustion_evidence", QualityClass.Q1)]
    inputs = {"explains": ["resource_exhaustion_evidence"]}
    create = calibrate(hypothesis, batch, inputs, PARAMS, None)
    assert create.target_type == "hypothesis"
    assert create.target_id == hypothesis.id
    assert create.tenant_id == hypothesis.tenant_id
    assert create.alpha == PARAMS.alpha


def test_calibration_justification_documents_params_and_components():
    hypothesis = make_hypothesis()
    batch = [
        make_evidence("resource_exhaustion_evidence", QualityClass.Q1),
        make_evidence("auth_anomaly_evidence", QualityClass.Q4),
    ]
    inputs = {"explains": ["resource_exhaustion_evidence"], "contradicts": []}
    create = calibrate(hypothesis, batch, inputs, PARAMS, [(0.5, 1), (0.5, 0)])
    j = create.calibration_justification
    assert j.strip()
    assert "alpha=0.5000" in j
    assert "M=10" in j
    assert "L0=0.0000" in j
    assert "S(H|E)=" in j
    assert "C(H)=" in j
    assert "ECE=" in j
    assert "C_final=" in j
    assert "nunca se ajusta" in j


def test_calibrate_differs_only_when_inputs_differ():
    hypothesis = make_hypothesis()
    batch = [make_evidence("resource_exhaustion_evidence", QualityClass.Q1)]
    strong = {"explains": ["resource_exhaustion_evidence"], "contradicts": []}
    weak = {"explains": [], "contradicts": []}
    a = build_confidence(calibrate(hypothesis, batch, strong, PARAMS, None))
    b = build_confidence(calibrate(hypothesis, batch, weak, PARAMS, None))
    assert a.id != b.id
    assert a.confidence_score != b.confidence_score


def test_historical_calibration_factor_empty_and_real():
    assert historical_calibration_factor(None, M=10) == (1.0, 0.0)
    assert historical_calibration_factor([], M=10) == (1.0, 0.0)
    hist, ece = historical_calibration_factor([(0.2, 0), (0.8, 1)], M=10)
    assert ece == pytest.approx(0.2, abs=1e-5)
    assert hist == pytest.approx(0.8, abs=1e-5)


def test_resolve_scope_evidence_follows_the_traceability_chain():
    ev1 = make_evidence("resource_exhaustion_evidence", QualityClass.Q1)
    ev2 = make_evidence("service_degradation_evidence", QualityClass.Q2)
    ev3 = make_evidence("auth_anomaly_evidence", QualityClass.Q4)
    anomaly_id = uuid.uuid4()
    context_id = uuid.uuid4()
    pattern_id = uuid.uuid4()
    hypothesis = Hypothesis(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        anomaly_ids=[anomaly_id],
        pattern_ids=[],
        description="Hipotesis.",
        predicted_consequences=["C."],
        falsification_criterion="F.",
        coherence_score=0.5,
        status=STATUS_CANDIDATE,
        generated_at=NOW,
    )
    anomalies = [
        Anomaly(
            id=anomaly_id,
            tenant_id=TENANT,
            context_id=context_id,
            pattern_id=pattern_id,
            deviation_score=2.5,
            tolerance_threshold=1.0,
            anomaly_class=ANOMALY_CLASS_POINT,
            detected_at=NOW,
        )
    ]
    contexts = [
        Context(
            id=context_id,
            tenant_id=TENANT,
            evidence_ids=[ev1.id, ev2.id],
            mental_model_id="resource_pressure",
            purpose="infrastructure_health",
            coherence_score=0.7,
            competing_models=[],
            activated_at=NOW,
        )
    ]
    evidence_by_id = {ev1.id: ev1, ev2.id: ev2, ev3.id: ev3}
    scope = resolve_scope_evidence(hypothesis, anomalies, contexts, evidence_by_id)
    assert sorted(e.id for e in scope) == sorted([ev1.id, ev2.id])
    assert ev3 not in scope