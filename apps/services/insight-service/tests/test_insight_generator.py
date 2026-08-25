"""Insight Generator tests - pure functions (no DB required)."""
import uuid
from datetime import UTC, datetime

import pytest
from libs.procedural_memory.insight_rules import INSIGHT_RULE_LIBRARY
from libs.reasoning.hypothesis import STATUS_CANDIDATE, Hypothesis
from libs.reasoning.insight import InsightCreate, build_insight, insight_id


@pytest.fixture
def sample_hypotheses():
    """Two competing hypotheses over the same anomaly (framework: premature convergence on a single is failure)."""
    hyp1 = Hypothesis(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        anomaly_ids=[uuid.uuid4()],
        pattern_ids=[],
        description="Test explanation 1",
        predicted_consequences=["obs1"],
        falsification_criterion="obs1 not observed",
        coherence_score=0.8,
        status=STATUS_CANDIDATE,
        generated_at=datetime.now(UTC),
    )
    hyp2 = Hypothesis(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        anomaly_ids=[uuid.uuid4()],
        pattern_ids=[],
        description="Test explanation 2",
        predicted_consequences=["obs2"],
        falsification_criterion="obs2 not observed",
        coherence_score=0.7,
        status=STATUS_CANDIDATE,
        generated_at=datetime.now(UTC),
    )
    return [hyp1, hyp2]


def test_insight_id_deterministic():
    """The same restructuring over the same knowledge yields the same deterministic id."""
    tid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    ctx_id = uuid.uuid4()
    hyp_ids = [uuid.uuid4(), uuid.uuid4()]
    desc = "Test restructuring description"
    iid1 = insight_id(tid, ctx_id, hyp_ids, desc)
    iid2 = insight_id(tid, ctx_id, hyp_ids, desc)
    assert iid1 == iid2
    # Different description → different id
    iid3 = insight_id(tid, ctx_id, hyp_ids, "Different description")
    assert iid1 != iid3


def test_insight_rule_fires_at_least_two():
    """The MVP rule fires only when min_hypotheses (2) are present."""
    rule = INSIGHT_RULE_LIBRARY[0]
    assert rule.min_hypotheses == 2


def test_build_insight_requires_facts():
    """build_insight from libs.reasoning.insight works with any valid InsightCreate."""
    tid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    ctx_id = uuid.uuid4()
    hyp_ids = [uuid.uuid4(), uuid.uuid4()]
    create = InsightCreate(
        tenant_id=tid,
        context_id=ctx_id,
        hypothesis_ids=hyp_ids,
        description="A new organization of existing knowledge.",
        prior_understanding="Prior understanding.",
        mental_model_update={"frame": "test-frame"},
    )
    insight = build_insight(create)
    assert insight.id is not None
    assert insight.description == create.description
    assert insight.prior_understanding == create.prior_understanding
    assert insight.mental_model_update == create.mental_model_update