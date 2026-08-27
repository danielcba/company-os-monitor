"""Unit tests for Pattern Refinement (P7 + P4) — pure logic, no IO.

The capability consumes the gateway read-store contract (dict payloads), so the
tests exercise the pure functions with dicts in that exact shape.
"""
from __future__ import annotations

import uuid

from libs.memory.pattern_refinement import (
    MIN_SAMPLES_FOR_REFINEMENT,
    DEACTIVATE_THRESHOLD,
    PatternRefinementStore,
    _attribute_outcomes,
    _refine_pattern,
    build_pattern_refinement,
)


def _decision(
    decision_id: str,
    recommendation_id: str,
    *,
    correct: bool | None = None,
    metric: str = "m1",
    prediction: float = 0.8,
) -> dict[str, object]:
    """Build a Decision payload. ``correct=None`` => no actual_outcomes."""
    actual_outcomes = None
    if correct is not None:
        actual_outcomes = [{"verifiable_by": metric, "value": 1 if correct else 0}]
    return {
        "id": decision_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "recommendation_id": recommendation_id,
        "expected_outcomes": [{"verifiable_by": metric, "predictiction": prediction}],
        "actual_outcomes": actual_outcomes,
    }


def _recommendation(rec_id: str, hypothesis_id: str) -> dict[str, object]:
    return {
        "id": rec_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "hypothesis_id": hypothesis_id,
    }


def _hypothesis(hyp_id: str, pattern_ids: list[str]) -> dict[str, object]:
    return {
        "id": hyp_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "pattern_ids": pattern_ids,
    }


def _pattern(pattern_id: str, *, strength: float = 0.9) -> dict[str, object]:
    return {
        "id": pattern_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "context_id": "00000000-0000-0000-0000-000000000002",
        "pattern_type": "correlation",
        "strength_measure": strength,
    }


def test_attribute_outcomes_counts_corroborated_and_contradicted():
    p1 = str(uuid.uuid4())
    h1 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    d1 = _decision(str(uuid.uuid4()), r1, correct=True)
    d2 = _decision(str(uuid.uuid4()), r1, correct=False)
    rec = _recommendation(r1, h1)
    hyp = _hypothesis(h1, [p1])
    pat = _pattern(p1)

    attr = _attribute_outcomes([d1, d2], [rec], [hyp], [pat])
    assert attr[p1]["corroborated"] == 1
    assert attr[p1]["contradicted"] == 1
    assert attr[p1]["linked"] == 2


def test_attribute_outcomes_skips_missing_actuals():
    p1 = str(uuid.uuid4())
    h1 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    d1 = _decision(str(uuid.uuid4()), r1, correct=None)  # no actual_outcomes
    rec = _recommendation(r1, h1)
    hyp = _hypothesis(h1, [p1])
    pat = _pattern(p1)

    attr = _attribute_outcomes([d1], [rec], [hyp], [pat])
    # No outcomes recorded => pattern not attributed (defensive: skip).
    assert p1 not in attr


def test_attribute_outcomes_skips_broken_chain():
    p1 = str(uuid.uuid4())
    h1 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    d1 = _decision(str(uuid.uuid4()), str(uuid.uuid4()), correct=True)  # rec missing
    rec = _recommendation(r1, h1)
    hyp = _hypothesis(h1, [p1])
    pat = _pattern(p1)

    attr = _attribute_outcomes([d1], [rec], [hyp], [pat])
    assert p1 not in attr


def test_refine_pattern_keep_when_few_samples():
    pat = _pattern(str(uuid.uuid4()), strength=0.9)
    # Only 1 decided outcome => below MIN_SAMPLES_FOR_REFINEMENT => keep.
    attr = {"corroborated": 1, "contradicted": 0, "inconclusive": 0, "linked": 1}
    res = _refine_pattern(pat, attr)
    assert res.recommended_action == "keep"
    assert res.recommended_strength == 0.9


def test_refine_pattern_deactivate_on_high_contradiction():
    pat = _pattern(str(uuid.uuid4()), strength=0.9)
    attr = {"corroborated": 1, "contradicted": 3, "inconclusive": 0, "linked": 4}
    res = _refine_pattern(pat, attr)
    assert res.contradiction_ratio == 0.75
    assert res.recommended_action == "deactivate"
    assert res.recommended_strength == 0.0


def test_refine_pattern_degrade_on_some_contradiction():
    pat = _pattern(str(uuid.uuid4()), strength=1.0)
    attr = {"corroborated": 3, "contradicted": 1, "inconclusive": 0, "linked": 4}
    res = _refine_pattern(pat, attr)
    assert res.contradiction_ratio == 0.25
    assert res.recommended_action == "degrade"
    assert res.recommended_strength == 0.75


def test_refine_pattern_inconclusive_never_counted_as_contradiction():
    pat = _pattern(str(uuid.uuid4()), strength=0.9)
    # All linked decisions inconclusive (no actuals) => 0 decided => keep.
    attr = {"corroborated": 0, "contradicted": 0, "inconclusive": 5, "linked": 5}
    res = _refine_pattern(pat, attr)
    assert res.contradiction_ratio == 0.0
    assert res.recommended_action == "keep"


def test_refine_pattern_no_fabrication_low_samples_with_contradiction():
    pat = _pattern(str(uuid.uuid4()), strength=0.9)
    # Only 1 decided outcome but contradicted => below threshold => keep.
    attr = {"corroborated": 0, "contradicted": 1, "inconclusive": 0, "linked": 1}
    res = _refine_pattern(pat, attr)
    assert res.recommended_action == "keep"
    assert res.recommended_strength == 0.9


class _DecisionStore:
    def __init__(self, payload):
        self._p = payload

    async def list_decisions(self, *, tenant_id, limit=50, offset=0):
        return self._p


class _RecStore:
    def __init__(self, payload):
        self._p = payload

    async def list_recommendations(self, *, tenant_id, limit=50, offset=0):
        return self._p


class _HypStore:
    def __init__(self, payload):
        self._p = payload

    async def list_hypotheses(self, *, tenant_id, limit=50, offset=0):
        return self._p


class _PatStore:
    def __init__(self, payload):
        self._p = payload

    async def list_patterns(self, *, tenant_id, limit=50, offset=0):
        return self._p


async def test_build_pattern_refinement_full_chain():
    p1 = str(uuid.uuid4())
    p2 = str(uuid.uuid4())
    h1 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    d_corr = _decision(str(uuid.uuid4()), r1, correct=True)
    d_contr = _decision(str(uuid.uuid4()), r1, correct=False)
    rec = _recommendation(r1, h1)
    hyp = _hypothesis(h1, [p1, p2])
    pat1 = _pattern(p1)
    pat2 = _pattern(p2)

    store = PatternRefinementStore(
        decision_store=_DecisionStore({"decisions": [d_corr, d_contr]}),
        recommendation_store=_RecStore({"recommendations": [rec]}),
        hypothesis_store=_HypStore({"hypotheses": [hyp]}),
        pattern_store=_PatStore({"patterns": [pat1, pat2]}),
    )
    report = await store.refine_for_tenant(tenant_id=uuid.UUID(int=1))
    by_pattern = {r.pattern_id: r for r in report.results}
    assert report.total_patterns == 2
    assert report.patterns_with_outcomes == 2
    # Both patterns share the same hypothesis => both get corr+contr.
    assert by_pattern[uuid.UUID(p1)].corroborated == 1
    assert by_pattern[uuid.UUID(p1)].contradicted == 1
    assert by_pattern[uuid.UUID(p2)].corroborated == 1
    assert by_pattern[uuid.UUID(p2)].contradicted == 1


async def test_build_pattern_refinement_empty_is_safe():
    store = PatternRefinementStore(
        decision_store=_DecisionStore({}),
        recommendation_store=_RecStore({}),
        hypothesis_store=_HypStore({}),
        pattern_store=_PatStore({}),
    )
    report = await store.refine_for_tenant(tenant_id=uuid.UUID(int=1))
    assert report.total_patterns == 0
    assert report.results == []
