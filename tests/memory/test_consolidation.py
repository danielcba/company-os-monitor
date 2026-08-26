"""Unit tests for the Memory (P7) Outcome Consolidation read/compute layer.

Pure, no IO. Focuses on framework conformance:
- P1 (no fabrication): missing/unclear actuals -> inconclusive, never failure.
- R1 (single capability): only consolidates expected vs actual outcomes.
- Tenant scope: cross-tenant batch is rejected.
- Determinism: same input -> identical (frozen) report.
"""
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from libs.memory.consolidation import (
    CrossTenantConsolidationError,
    build_consolidation,
    consolidate_decisions,
)


def _decision(*, tenant_id, expected_outcomes, actual_outcomes, decision_id=None):
    return SimpleNamespace(
        id=decision_id or uuid.uuid4(),
        tenant_id=tenant_id,
        expected_outcomes=expected_outcomes,
        actual_outcomes=actual_outcomes,
    )


TENANT = uuid.uuid4()


def test_missing_actuals_is_inconclusive_not_fabricated_failure():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=None,
    )
    result = build_consolidation(decision)
    assert result.has_actuals is False
    assert result.inconclusive == 1
    assert result.corroborated == 0
    assert result.contradicted == 0
    assert result.calibration_feedback == 0.0
    assert result.brier is None
    assert result.ece is None


def test_empty_actuals_list_is_inconclusive():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=[],
    )
    result = build_consolidation(decision)
    assert result.has_actuals is False
    assert result.inconclusive == 1


def test_corroborated_when_prediction_matches_observed():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"},
            {"verifiable_by": "churn", "prediction": 0.1, "deadline": "2026-09-01"},
        ],
        actual_outcomes=[
            {"verifiable_by": "revenue", "value": True},
            {"verifiable_by": "churn", "value": False},
        ],
    )
    result = build_consolidation(decision)
    assert result.corroborated == 2  # noqa: PLR2004
    assert result.contradicted == 0
    assert result.inconclusive == 0
    assert result.calibration_feedback == 1.0
    assert result.brier is not None
    # Brier = mean((p-o)^2) = ((0.9-1)^2 + (0.1-0)^2)/2 = 0.01 (lower is better)
    assert result.brier == pytest.approx(0.01)


def test_contradicted_when_prediction_mismatches_observed():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=[{"verifiable_by": "revenue", "value": False}],
    )
    result = build_consolidation(decision)
    assert result.contradicted == 1
    assert result.corroborated == 0
    assert result.calibration_feedback == -1.0


def test_unparseable_actual_is_inconclusive_not_fabricated():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=[{"verifiable_by": "revenue", "value": "maybe-soon"}],
    )
    result = build_consolidation(decision)
    assert result.inconclusive == 1
    assert result.contradicted == 0
    assert result.corroborated == 0


def test_actual_without_matching_expected_is_ignored():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=[
            {"verifiable_by": "revenue", "value": True},
            {"verifiable_by": "unknown_metric", "value": False},
        ],
    )
    result = build_consolidation(decision)
    assert result.corroborated == 1
    assert result.inconclusive == 0


def test_cross_tenant_batch_rejected():
    other = uuid.uuid4()
    decisions = [
        _decision(
            tenant_id=TENANT,
            expected_outcomes=[],
            actual_outcomes=[],
        ),
        _decision(
            tenant_id=other,
            expected_outcomes=[],
            actual_outcomes=[],
        ),
    ]
    with pytest.raises(CrossTenantConsolidationError):
        consolidate_decisions(TENANT, decisions)


def test_deterministic_report_is_frozen_and_stable():
    decision = _decision(
        tenant_id=TENANT,
        expected_outcomes=[
            {"verifiable_by": "revenue", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=[{"verifiable_by": "revenue", "value": True}],
    )
    report_a = consolidate_decisions(TENANT, [decision])
    report_b = consolidate_decisions(TENANT, [decision])
    assert report_a == report_b
    # frozen model cannot be mutated
    with pytest.raises(ValidationError):
        report_a.aggregate_feedback = 0.5


def test_aggregate_rollup_across_multiple_decisions():
    d1 = _decision(
        tenant_id=TENANT,
        expected_outcomes=[{"verifiable_by": "a", "prediction": 0.9}],
        actual_outcomes=[{"verifiable_by": "a", "value": True}],
    )
    d2 = _decision(
        tenant_id=TENANT,
        expected_outcomes=[{"verifiable_by": "b", "prediction": 0.1}],
        actual_outcomes=[{"verifiable_by": "b", "value": True}],  # mismatch
    )
    report = consolidate_decisions(TENANT, [d1, d2])
    expected_count = 2
    assert report.total_decisions == expected_count
    assert report.decisions_with_actuals == expected_count
    assert report.corroborated == 1
    assert report.contradicted == 1
    assert report.inconclusive == 0
    assert report.aggregate_feedback == 0.0
