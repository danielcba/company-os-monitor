"""Unit tests for the Learning Loop (P7 feedback mechanism).

Pure, no IO. Focuses on framework conformance:
- P7: closing the learning loop (outcome → confidence calibration)
- P1: no fabrication of missing outcomes (inconclusive → None)
- R1: single capability (compute learning signal)
"""
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from libs.learning.learning_loop import (
    build_learning_history,
    compute_outcome_signal,
)


def _decision(
    *, tenant_id, expected_outcomes, actual_outcomes, confidence_id=None, decision_id=None
):
    return SimpleNamespace(
        id=decision_id or uuid.uuid4(),
        tenant_id=tenant_id,
        expected_outcomes=expected_outcomes,
        actual_outcomes=actual_outcomes,
        confidence_id=confidence_id or uuid.uuid4(),
    )


def _confidence(*, confidence_score, cid=None):
    return SimpleNamespace(
        id=cid or uuid.uuid4(),
        confidence_score=confidence_score,
    )


TENANT = uuid.uuid4()


def test_outcome_signal_corroborated():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=[{"verifiable_by": "revenue", "value": True}],
    )
    assert compute_outcome_signal(decision) == 1


def test_outcome_signal_contradicted():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=[{"verifiable_by": "revenue", "value": False}],
    )
    assert compute_outcome_signal(decision) == 0


def test_outcome_signal_no_actuals_returns_none():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=None,
    )
    assert compute_outcome_signal(decision) is None


def test_outcome_signal_no_expected_returns_none():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[],
        actual_outcomes=[{"verifiable_by": "revenue", "value": True}],
    )
    assert compute_outcome_signal(decision) is None


def test_outcome_signal_unparseable_actual_returns_none():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=[{"verifiable_by": "revenue", "value": "indeterminate"}],
    )
    assert compute_outcome_signal(decision) is None


def test_outcome_signal_mixed_corroborated_wins():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "a", "prediction": 0.9},
            {"verifiable_by": "b", "prediction": 0.1},
        ],
        actual_outcomes=[
            {"verifiable_by": "a", "value": True},
            {"verifiable_by": "b", "value": False},
        ],
    )
    assert compute_outcome_signal(decision) == 1


def test_outcome_signal_mixed_contradicted_wins():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "a", "prediction": 0.9},
            {"verifiable_by": "b", "prediction": 0.1},
        ],
        actual_outcomes=[
            {"verifiable_by": "a", "value": False},
            {"verifiable_by": "b", "value": True},
        ],
    )
    assert compute_outcome_signal(decision) == 0


def test_learning_history_builds_pairs():
    cid_a = uuid.uuid4()
    cid_b = uuid.uuid4()
    decisions = [
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[{"verifiable_by": "a", "prediction": 0.9}],
            actual_outcomes=[{"verifiable_by": "a", "value": True}],
            confidence_id=cid_a,
        ),
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[{"verifiable_by": "b", "prediction": 0.1}],
            actual_outcomes=[{"verifiable_by": "b", "value": True}],
            confidence_id=cid_b,
        ),
    ]
    confidences = [
        _confidence(confidence_score=0.8, cid=cid_a),
        _confidence(confidence_score=0.2, cid=cid_b),
    ]
    history = build_learning_history(TENANT, decisions, confidences)
    expected_count = 2
    score_high = 0.8
    score_low = 0.2
    assert history.total_decisions_with_outcomes == expected_count
    assert len(history.pairs) == expected_count
    assert history.pairs[0].confidence_score == score_high
    assert history.pairs[0].outcome == 1
    assert history.pairs[1].confidence_score == score_low
    assert history.pairs[1].outcome == 0


def test_learning_history_skips_inconclusive():
    cid = uuid.uuid4()
    decisions = [
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[{"verifiable_by": "a", "prediction": 0.9}],
            actual_outcomes=None,  # inconclusive
            confidence_id=cid,
        ),
    ]
    confidences = [_confidence(confidence_score=0.8, cid=cid)]
    history = build_learning_history(TENANT, decisions, confidences)
    assert history.total_decisions_with_outcomes == 0
    assert len(history.pairs) == 0
    assert history.ece is None


def test_learning_history_ece_computed_with_enough_data():
    cid_a = uuid.uuid4()
    cid_b = uuid.uuid4()
    decisions = [
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[{"verifiable_by": "a", "prediction": 0.9}],
            actual_outcomes=[{"verifiable_by": "a", "value": True}],
            confidence_id=cid_a,
        ),
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[{"verifiable_by": "b", "prediction": 0.1}],
            actual_outcomes=[{"verifiable_by": "b", "value": True}],
            confidence_id=cid_b,
        ),
    ]
    confidences = [
        _confidence(confidence_score=0.8, cid=cid_a),
        _confidence(confidence_score=0.2, cid=cid_b),
    ]
    history = build_learning_history(TENANT, decisions, confidences)
    assert history.ece is not None
    assert history.historical_calibration is not None
    assert 0.0 <= history.ece <= 1.0
    assert 0.0 <= history.historical_calibration <= 1.0
    assert history.historical_calibration == pytest.approx(1.0 - history.ece)


def test_learning_history_insufficient_data_no_ece():
    cid = uuid.uuid4()
    decisions = [
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[{"verifiable_by": "a", "prediction": 0.9}],
            actual_outcomes=[{"verifiable_by": "a", "value": True}],
            confidence_id=cid,
        ),
    ]
    confidences = [_confidence(confidence_score=0.8, cid=cid)]
    history = build_learning_history(TENANT, decisions, confidences)
    assert history.ece is None
    assert history.historical_calibration is None


def test_learning_history_missing_confidence_skipped():
    cid_missing = uuid.uuid4()  # not in confidences list
    decisions = [
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[{"verifiable_by": "a", "prediction": 0.9}],
            actual_outcomes=[{"verifiable_by": "a", "value": True}],
            confidence_id=cid_missing,
        ),
    ]
    confidences = []  # confidence not found
    history = build_learning_history(TENANT, decisions, confidences)
    assert history.total_decisions_with_outcomes == 0


def test_learning_history_is_frozen():
    cid = uuid.uuid4()
    decisions = [
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[{"verifiable_by": "a", "prediction": 0.9}],
            actual_outcomes=[{"verifiable_by": "a", "value": True}],
            confidence_id=cid,
        ),
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[{"verifiable_by": "b", "prediction": 0.1}],
            actual_outcomes=[{"verifiable_by": "b", "value": False}],
            confidence_id=cid,
        ),
    ]
    confidences = [_confidence(confidence_score=0.8, cid=cid)]
    history = build_learning_history(TENANT, decisions, confidences)
    with pytest.raises(ValidationError):
        history.ece = 0.5
