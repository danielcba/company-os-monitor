"""Unit tests for Insight Transformation journaling (R6) — pure logic, no IO.

The capability consumes the gateway read-store contract (dict payloads), so the
tests exercise the pure functions with dicts in that exact shape.
"""
from __future__ import annotations

import uuid

from libs.memory.insight_transformation import (
    InsightTransformationStore,
    _attribute_outcomes_to_insights,
    _classify_transformation,
    _journal_insight,
)


def _insight(insight_id, *, prior=None, updated=None, context_id=None):
    return {
        "id": insight_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "context_id": context_id,
        "description": "d",
        "prior_understanding": prior,
        "mental_model_update": updated,
    }


def _recommendation(rec_id, insight_id):
    return {
        "id": rec_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "insight_id": insight_id,
        "hypothesis_id": str(uuid.uuid4()),
    }


def _decision(decision_id, recommendation_id, *, correct=None):
    actual_outcomes = None
    if correct is not None:
        actual_outcomes = [{"verifiable_by": "m1", "value": 1 if correct else 0}]
    return {
        "id": decision_id,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "recommendation_id": recommendation_id,
        "expected_outcomes": [{"verifiable_by": "m1", "predictiction": 0.8}],
        "actual_outcomes": actual_outcomes,
    }


def test_classify_unchanged_when_both_blank():
    assert _classify_transformation(None, None) == "unchanged"
    assert _classify_transformation("", {}) == "unchanged"


def test_classify_revised_when_prior_differs_from_update():
    assert _classify_transformation("old", {"a": 1}) == "revised"
    assert _classify_transformation(None, {"a": 1}) == "revised"


def test_classify_stable_when_serialized_equal():
    # prior is a string whose repr equals the dict's repr => no perceived change.
    assert _classify_transformation("{'x': 1}", {"x": 1}) == "stable"


def test_attribute_links_decision_to_insight_via_recommendation():
    i1 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    d_corr = _decision(str(uuid.uuid4()), r1, correct=True)
    d_contr = _decision(str(uuid.uuid4()), r1, correct=False)
    rec = _recommendation(r1, i1)

    attr = _attribute_outcomes_to_insights([d_corr, d_contr], [rec])
    assert attr[i1]["corroborated"] == 1
    assert attr[i1]["contradicted"] == 1
    assert attr[i1]["linked"] == 2  # noqa: PLR2004
    assert attr[i1]["decisions_with_outcomes"] == 2  # noqa: PLR2004


def test_attribute_skips_recommendation_without_insight():
    r1 = str(uuid.uuid4())
    d = _decision(str(uuid.uuid4()), r1, correct=True)
    rec = _recommendation(r1, None)  # no insight link

    attr = _attribute_outcomes_to_insights([d], [rec])
    assert attr == {}


def test_journal_insight_records_transformation_and_outcomes():
    i1 = str(uuid.uuid4())
    ins = _insight(i1, prior="old view", updated={"new": "view"}, context_id=str(uuid.uuid4()))
    attr = {
        "corroborated": 1,
        "contradicted": 0,
        "inconclusive": 0,
        "linked": 1,
        "decisions_with_outcomes": 1,
    }

    res = _journal_insight(ins, linked_recommendations=2, attr=attr)
    assert res.transformation_kind == "revised"
    assert res.linked_recommendations == 2  # noqa: PLR2004
    assert res.corroborated == 1
    assert res.linked_decisions_with_outcomes == 1
    assert res.insight_id == uuid.UUID(i1)


class _Store:
    def __init__(self, payload):
        self._p = payload

    async def list_insights(self, *, tenant_id, limit=50, offset=0):
        return self._p

    async def list_recommendations(self, *, tenant_id, limit=50, offset=0):
        return self._p

    async def list_decisions(self, *, tenant_id, limit=50, offset=0):
        return self._p


async def test_build_insight_transformation_with_outcomes():
    i1 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())
    ins = _insight(i1, prior="old", updated={"new": 1}, context_id=str(uuid.uuid4()))
    rec = _recommendation(r1, i1)
    d_corr = _decision(str(uuid.uuid4()), r1, correct=True)
    d_contr = _decision(str(uuid.uuid4()), r1, correct=False)

    store = InsightTransformationStore(
        insight_store=_Store({"insights": [ins]}),
        decision_store=_Store({"decisions": [d_corr, d_contr]}),
        recommendation_store=_Store({"recommendations": [rec]}),
    )
    report = await store.journal_for_tenant(tenant_id=uuid.UUID(int=1))
    assert report.total_insights == 1
    res = report.results[0]
    assert res.transformation_kind == "revised"
    assert res.linked_recommendations == 1
    assert res.corroborated == 1
    assert res.contradicted == 1


async def test_build_insight_transformation_without_outcome_readers():
    i1 = str(uuid.uuid4())
    ins = _insight(i1, prior=None, updated=None, context_id=None)

    store = InsightTransformationStore(insight_store=_Store({"insights": [ins]}))
    report = await store.journal_for_tenant(tenant_id=uuid.UUID(int=1))
    assert report.total_insights == 1
    res = report.results[0]
    assert res.transformation_kind == "unchanged"
    assert res.corroborated == 0
    assert res.linked_recommendations == 0
