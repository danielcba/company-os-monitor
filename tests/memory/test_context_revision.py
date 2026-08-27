"""Unit tests for Context Revision (P7 + P2) — pure logic, no IO.

The capability consumes the gateway read-store contract (dict payloads), so the
tests exercise the pure functions with dicts in that exact shape.
"""
from __future__ import annotations

import uuid

from libs.memory.context_revision import (
    ContextRevisionStore,
    _attribute_outcomes_to_contexts,
    _revise_context,
)


def _decision(decision_id, recommendation_id, *, correct=None, metric="m1", prediction=0.8):
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


def _recommendation(rec_id, hypothesis_id):
    return {
        "id": rec_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "hypothesis_id": hypothesis_id,
    }


def _hypothesis(hyp_id, pattern_ids):
    return {
        "id": hyp_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "pattern_ids": pattern_ids,
    }


def _pattern(pattern_id, context_id, *, strength=0.9):
    return {
        "id": pattern_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "context_id": context_id,
        "pattern_type": "correlation",
        "strength_measure": strength,
    }


def _context(context_id, *, competing=None):
    return {
        "id": context_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "competing_models": competing or [],
        "is_active": True,
    }


def test_attribute_maps_decision_to_context_via_chain():
    c1 = str(uuid.uuid4())
    p1 = str(uuid.uuid4())
    h1 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    d_corr = _decision(str(uuid.uuid4()), r1, correct=True)
    d_contr = _decision(str(uuid.uuid4()), r1, correct=False)
    rec = _recommendation(r1, h1)
    hyp = _hypothesis(h1, [p1])
    pat = _pattern(p1, c1)

    attr = _attribute_outcomes_to_contexts([d_corr, d_contr], [rec], [hyp], [pat])
    assert attr[c1]["corroborated"] == 1
    assert attr[c1]["contradicted"] == 1
    assert attr[c1]["linked"] == 2  # noqa: PLR2004


def test_attribute_skips_missing_links():
    c1 = str(uuid.uuid4())
    p1 = str(uuid.uuid4())
    h1 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    # Decision points to a recommendation that is absent.
    d = _decision(str(uuid.uuid4()), str(uuid.uuid4()), correct=True)
    rec = _recommendation(r1, h1)
    hyp = _hypothesis(h1, [p1])
    pat = _pattern(p1, c1)

    attr = _attribute_outcomes_to_contexts([d], [rec], [hyp], [pat])
    assert c1 not in attr


def test_revise_context_keep_when_few_samples():
    ctx = _context(str(uuid.uuid4()), competing=[{"model_id": "alt-1"}])
    attr = {"corroborated": 1, "contradicted": 0, "inconclusive": 0, "linked": 1}
    res = _revise_context(ctx, attr)
    assert res.recommended_revision == "keep"
    assert res.suggested_competitor is None


def test_revise_context_consider_competitor_when_high_contradiction():
    ctx = _context(str(uuid.uuid4()), competing=[{"model_id": "alt-7"}])
    attr = {"corroborated": 1, "contradicted": 3, "inconclusive": 0, "linked": 4}
    res = _revise_context(ctx, attr)
    assert res.contradiction_ratio == 0.75  # noqa: PLR2004
    assert res.recommended_revision == "consider_competitor"
    assert res.suggested_competitor == "alt-7"
    assert res.has_competing_models is True


def test_revise_context_review_without_competing_models():
    ctx = _context(str(uuid.uuid4()), competing=[])
    attr = {"corroborated": 1, "contradicted": 3, "inconclusive": 0, "linked": 4}
    res = _revise_context(ctx, attr)
    assert res.recommended_revision == "review"
    assert res.suggested_competitor is None


def test_revise_context_no_fabrication_inconclusive_kept():
    ctx = _context(str(uuid.uuid4()), competing=[{"model_id": "alt-1"}])
    attr = {"corroborated": 0, "contradicted": 0, "inconclusive": 5, "linked": 5}
    res = _revise_context(ctx, attr)
    assert res.contradiction_ratio == 0.0
    assert res.recommended_revision == "keep"


def test_revise_context_uses_first_competitor_name():
    ctx = _context(str(uuid.uuid4()), competing=[{"name": "bayesian"}])
    attr = {"corroborated": 0, "contradicted": 2, "inconclusive": 0, "linked": 2}
    res = _revise_context(ctx, attr)
    assert res.recommended_revision == "consider_competitor"
    assert res.suggested_competitor == "bayesian"


class _Store:
    def __init__(self, payload):
        self._p = payload

    async def list_contexts(self, *, tenant_id, limit=50, offset=0):
        return self._p

    async def list_patterns(self, *, tenant_id, limit=50, offset=0):
        return self._p

    async def list_hypotheses(self, *, tenant_id, limit=50, offset=0):
        return self._p

    async def list_recommendations(self, *, tenant_id, limit=50, offset=0):
        return self._p

    async def list_decisions(self, *, tenant_id, limit=50, offset=0):
        return self._p


async def test_build_context_revision_full_chain():
    c1 = str(uuid.uuid4())
    p1 = str(uuid.uuid4())
    h1 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    d_corr = _decision(str(uuid.uuid4()), r1, correct=True)
    d_contr = _decision(str(uuid.uuid4()), r1, correct=False)
    rec = _recommendation(r1, h1)
    hyp = _hypothesis(h1, [p1])
    pat = _pattern(p1, c1)
    ctx = _context(c1, competing=[{"model_id": "alt-9"}])

    store = ContextRevisionStore(
        decision_store=_Store({"decisions": [d_corr, d_contr]}),
        recommendation_store=_Store({"recommendations": [rec]}),
        hypothesis_store=_Store({"hypotheses": [hyp]}),
        pattern_store=_Store({"patterns": [pat]}),
        context_store=_Store({"contexts": [ctx]}),
    )
    report = await store.revise_for_tenant(tenant_id=uuid.UUID(int=1))
    assert report.total_contexts == 1
    assert report.contexts_with_outcomes == 1
    res = report.results[0]
    assert res.context_id == uuid.UUID(c1)
    assert res.corroborated == 1
    assert res.contradicted == 1
    assert res.recommended_revision == "consider_competitor"
    assert res.suggested_competitor == "alt-9"


async def test_build_context_revision_empty_is_safe():
    store = ContextRevisionStore(
        decision_store=_Store({}),
        recommendation_store=_Store({}),
        hypothesis_store=_Store({}),
        pattern_store=_Store({}),
        context_store=_Store({}),
    )
    report = await store.revise_for_tenant(tenant_id=uuid.UUID(int=1))
    assert report.total_contexts == 0
    assert report.results == []
