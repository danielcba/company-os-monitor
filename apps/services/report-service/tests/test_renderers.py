"""Unit tests for the report renderers (pure, no I/O).

Covers the Executive / Technical / JSON renderers against a known pipeline
input, the empty-input behavior ("0 decisiones" without errors) and the
ADR-0002 anti-bypass contract: the report contains EXACTLY the data persisted
in the tables and never invents judgments.
"""
import uuid
from datetime import UTC, date, datetime
from typing import Any

from libs.action.decision import STATUS_COMMITTED, Decision
from libs.action.recommendation import STATUS_PROPOSED, Recommendation
from libs.learning.confidence import Confidence
from libs.perception.context import Context
from libs.perception.evidence import Evidence
from libs.perception.observation import QualityClass
from libs.reasoning.anomaly import Anomaly
from libs.reasoning.hypothesis import STATUS_CANDIDATE, Hypothesis
from libs.reasoning.pattern import Pattern

from src.renderers.common import ReportSource, build_decision_traces
from src.renderers.executive import render_executive
from src.renderers.json_render import render_json
from src.renderers.technical import render_technical

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
PERIOD_START = date(2026, 8, 10)
PERIOD_END = date(2026, 8, 17)


def make_confidence(score: float = 0.82, **overrides: Any) -> Confidence:
    base = {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "target_type": "hypothesis",
        "target_id": uuid.uuid4(),
        "evidential_support": 0.7,
        "explanatory_coherence": 0.8,
        "historical_calibration": 1.0,
        "confidence_score": score,
        "alpha": 0.5,
        "calibration_justification": (
            f"S=0.7000, C=0.8000, ECE=0.0000, C_final={score}."
        ),
        "calibration_error_estimate": 0.0,
        "computed_at": NOW,
    }
    base.update(overrides)
    return Confidence(**base)


def make_hypothesis(**overrides: Any) -> Hypothesis:
    base = {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "anomaly_ids": [],
        "pattern_ids": [],
        "description": "Hipotesis de saturacion de disco.",
        "predicted_consequences": ["El volumen persistido seguira creciendo."],
        "falsification_criterion": "Si no se observa, se descarta.",
        "coherence_score": 0.5,
        "status": STATUS_CANDIDATE,
        "generated_at": NOW,
    }
    base.update(overrides)
    return Hypothesis(**base)


def make_recommendation(
    hypothesis: Hypothesis, confidence: Confidence, **overrides: Any
) -> Recommendation:
    base = {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "hypothesis_id": hypothesis.id,
        "insight_id": None,
        "confidence_id": confidence.id,
        "action_description": "Expandir el volumen objetivo del almacenamiento.",
        "rationale": "Derivada de la hipotesis y su confidence calibrada.",
        "expected_consequences": ["El espacio libre permanecera por encima del umbral."],
        "alternatives_considered": [
            {
                "action": "compress",
                "rationale": "Menor coste inmediato.",
                "rejected_reason": "Puede no acompanar el ritmo de crecimiento.",
                "confidence": confidence.confidence_score,
            }
        ],
        "confidence_score": confidence.confidence_score,
        "status": STATUS_PROPOSED,
        "proposed_at": NOW,
    }
    base.update(overrides)
    return Recommendation(**base)


def make_decision(
    recommendation: Recommendation,
    confidence: Confidence,
    risk_tolerance: str = "medium",
    **overrides: Any,
) -> Decision:
    base = {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "recommendation_id": recommendation.id,
        "confidence_id": confidence.id,
        "authority_id": uuid.uuid4(),
        "commitment": (
            "Expandir el volumen objetivo del almacenamiento antes del umbral "
            "proyectado. Compromiso registrado bajo autoridad."
        ),
        "expected_outcomes": [
            {
                "prediction": "El espacio libre permanecera por encima del umbral.",
                "verifiable_by": "disk_free_percent",
                "deadline": "2026-11-15",
            }
        ],
        "risk_tolerance": risk_tolerance,
        "status": STATUS_COMMITTED,
        "committed_at": NOW,
        "executed_at": None,
        "actual_outcomes": None,
    }
    base.update(overrides)
    return Decision(**base)


def make_chain(
    confidence_score: float = 0.82, risk_tolerance: str = "medium"
) -> dict[str, Any]:
    hypothesis = make_hypothesis()
    confidence = make_confidence(score=confidence_score, target_id=hypothesis.id)
    recommendation = make_recommendation(hypothesis, confidence)
    decision = make_decision(recommendation, confidence, risk_tolerance)
    return {
        "decision": decision,
        "recommendation": recommendation,
        "confidence": confidence,
        "hypothesis": hypothesis,
    }


def make_source(
    chain: dict[str, Any] | None = None,
    extra_confidences: tuple[Confidence, ...] = (),
    extra_hypotheses: tuple[Hypothesis, ...] = (),
) -> ReportSource:
    chain = chain or make_chain()
    return ReportSource(
        tenant={"id": TENANT, "name": "Sandbox Tenant", "slug": "sandbox"},
        decisions=(chain["decision"],),
        recommendations=(chain["recommendation"],),
        contexts=(),
        confidences=(chain["confidence"], *extra_confidences),
        hypotheses=(chain["hypothesis"], *extra_hypotheses),
        anomalies=(),
        patterns=(),
        evidence=(),
        observations=(),
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        generated_at=NOW,
    )


def test_executive_renders_known_fields():
    chain = make_chain(confidence_score=0.82)
    doc = render_executive(make_source(chain))
    assert doc["report_type"] == "executive"
    assert doc["decision_count"] == 1
    assert doc["tenant"]["name"] == "Sandbox Tenant"
    assert doc["period"]["start"] == PERIOD_START.isoformat()
    assert doc["period"]["end"] == PERIOD_END.isoformat()
    assert len(doc["top_decisions"]) == 1
    top = doc["top_decisions"][0]
    assert top["decision_id"] == str(chain["decision"].id)
    assert top["commitment"] == chain["decision"].commitment
    assert top["risk_tolerance"] == chain["decision"].risk_tolerance
    assert top["confidence"] == 0.82
    assert top["expected_outcome_count"] == len(chain["decision"].expected_outcomes)
    assert top["action"] == chain["recommendation"].action_description


def test_executive_empty_inputs_render_zero_decisions():
    source = ReportSource(
        tenant={"id": TENANT, "name": "Sandbox Tenant", "slug": "sandbox"},
        decisions=(),
        recommendations=(),
        contexts=(),
        confidences=(),
        hypotheses=(),
        anomalies=(),
        patterns=(),
        evidence=(),
        observations=(),
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        generated_at=NOW,
    )
    doc = render_executive(source)
    assert doc["decision_count"] == 0
    assert doc["top_decisions"] == []
    assert doc["future_risks"] == []
    assert doc["pending_authority"] == []


def test_executive_future_risks_only_above_threshold():
    high = make_hypothesis(description="Riesgo de saturacion inminente.")
    low = make_hypothesis(description="Riesgo menor sin evidencia suficiente.")
    conf_high = make_confidence(score=0.8, target_id=high.id)
    conf_low = make_confidence(score=0.5, target_id=low.id)
    chain = make_chain()
    source = make_source(
        chain,
        extra_confidences=(conf_high, conf_low),
        extra_hypotheses=(high, low),
    )
    doc = render_executive(source, risk_threshold=0.6)
    descriptions = [r["description"] for r in doc["future_risks"]]
    assert high.description in descriptions
    assert low.description not in descriptions


def test_executive_pending_authority_only_high_risk():
    low_chain = make_chain(confidence_score=0.82, risk_tolerance="medium")
    high_chain = make_chain(confidence_score=0.92, risk_tolerance="high")
    source = ReportSource(
        tenant={"id": TENANT, "name": "Sandbox Tenant", "slug": "sandbox"},
        decisions=(low_chain["decision"], high_chain["decision"]),
        recommendations=(
            low_chain["recommendation"],
            high_chain["recommendation"],
        ),
        contexts=(),
        confidences=(low_chain["confidence"], high_chain["confidence"]),
        hypotheses=(low_chain["hypothesis"], high_chain["hypothesis"]),
        anomalies=(),
        patterns=(),
        evidence=(),
        observations=(),
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        generated_at=NOW,
    )
    doc = render_executive(source)
    pending = [p["decision_id"] for p in doc["pending_authority"]]
    assert pending == [str(high_chain["decision"].id)]


def test_executive_is_adr0002_faithful_no_invented_judgments():
    """The executive report formats EXACTLY the persisted data (no cost/ROI
    invention, no new judgments)."""
    chain = make_chain(confidence_score=0.82)
    doc = render_executive(make_source(chain))
    top = doc["top_decisions"][0]
    assert top["commitment"] == chain["decision"].commitment
    assert top["confidence"] == chain["confidence"].confidence_score
    assert top["risk_tolerance"] == chain["decision"].risk_tolerance
    assert "cost" not in top
    assert "roi" not in top


def test_technical_renders_all_sections_with_exact_data():
    chain = make_chain(confidence_score=0.82)
    doc = render_technical(make_source(chain))
    assert doc["report_type"] == "technical"
    assert doc["decision_count"] == 1
    assert len(doc["section_1_cognitive_trace"]) == 1
    assert len(doc["section_2_evidence_chain"]) == 1
    assert len(doc["section_3_reasoning_chain"]) == 1
    assert len(doc["section_4_confidence_calibration"]) == 1
    assert len(doc["section_5_recommendation_and_alternatives"]) == 1
    assert len(doc["section_6_decision_and_expected_outcomes"]) == 1
    # SECTION 7 (Learning Loop) is populated per decision that declares expected
    # outcomes: it is the expected-vs-actual comparison (Brier/ECE update).
    assert len(doc["section_7_learning_loop"]) == doc["decision_count"]
    learning = doc["section_7_learning_loop"][0]
    assert learning["outcome_count"] == len(chain["decision"].expected_outcomes)
    assert "brier_score" in learning
    assert "historical_calibration" in learning

    s1 = doc["section_1_cognitive_trace"][0]
    assert s1["decision_id"] == str(chain["decision"].id)
    assert s1["authority_id"] == str(chain["decision"].authority_id)
    assert s1["risk_tolerance"] == chain["decision"].risk_tolerance
    assert s1["confidence"] == chain["confidence"].confidence_score

    s4 = doc["section_4_confidence_calibration"][0]["confidence"]
    assert s4["evidential_support"] == chain["confidence"].evidential_support
    assert s4["explanatory_coherence"] == chain["confidence"].explanatory_coherence
    assert s4["historical_calibration"] == chain["confidence"].historical_calibration
    assert s4["confidence_score"] == chain["confidence"].confidence_score
    assert s4["alpha"] == chain["confidence"].alpha

    s5 = doc["section_5_recommendation_and_alternatives"][0]["recommendation"]
    assert s5["action_description"] == chain["recommendation"].action_description
    assert s5["rationale"] == chain["recommendation"].rationale
    assert s5["alternatives_considered"] == chain["recommendation"].alternatives_considered
    assert s5["expected_consequences"] == chain["recommendation"].expected_consequences

    s6 = doc["section_6_decision_and_expected_outcomes"][0]
    assert s6["commitment"] == chain["decision"].commitment
    assert s6["expected_outcomes"] == chain["decision"].expected_outcomes
    assert s6["actual_outcomes"] is None


def test_technical_empty_inputs_render_zero_decisions_without_error():
    source = ReportSource(
        tenant={"id": TENANT, "name": "Sandbox Tenant", "slug": "sandbox"},
        decisions=(),
        recommendations=(),
        contexts=(),
        confidences=(),
        hypotheses=(),
        anomalies=(),
        patterns=(),
        evidence=(),
        observations=(),
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        generated_at=NOW,
    )
    doc = render_technical(source)
    assert doc["decision_count"] == 0
    for key, value in doc.items():
        if key.startswith("section_") and key != "section_7_learning_loop":
            assert value == []
    assert doc["section_7_learning_loop"] == []


def test_json_renderer_pure_structure_matches_inputs():
    chain = make_chain(confidence_score=0.82)
    source = make_source(chain)
    doc = render_json(source)
    assert doc["report_type"] == "json"
    assert doc["decision_count"] == 1
    trace = doc["decision_traces"][0]
    assert trace["decision"]["id"] == str(chain["decision"].id)
    assert trace["decision"]["commitment"] == chain["decision"].commitment
    assert trace["decision"]["expected_outcomes"] == chain["decision"].expected_outcomes
    assert trace["confidence"]["confidence_score"] == 0.82
    assert trace["recommendation"]["id"] == str(chain["recommendation"].id)
    assert trace["hypothesis"]["id"] == str(chain["hypothesis"].id)
    assert doc["recommendations"][0]["action_description"] == (
        chain["recommendation"].action_description
    )


def test_build_decision_traces_correlates_full_chain():
    """decision -> recommendation -> hypothesis correlation resolves the
    decision's confidence and recommendation (ADR-0002: data from the tables)."""
    chain = make_chain()
    trace = build_decision_traces(make_source(chain))[0]
    assert trace["decision"]["id"] == str(chain["decision"].id)
    assert trace["confidence"]["id"] == str(chain["confidence"].id)
    assert trace["recommendation"]["id"] == str(chain["recommendation"].id)
    assert trace["hypothesis"]["id"] == str(chain["hypothesis"].id)
    assert trace["anomalies"] == []
    assert trace["evidence"] == []


def test_build_decision_traces_includes_evidence_chain():
    """A decision whose trace includes anomaly -> pattern -> context -> evidence
    -> observations renders the full Evidence Chain from the tables."""
    obs = {
        "id": uuid.uuid4(),
        "fact_type": "disk_usage_percent",
        "fact_value": {"value": 0.88},
        "unit": "percent",
        "captured_at": NOW,
        "quality_class": "Q1",
    }
    evidence = Evidence(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        observation_ids=[obs["id"]],
        organization_type="resource_exhaustion_evidence",
        description="organizacion factual",
        quality_class=QualityClass.Q1,
        weight=0.88,
        organized_at=NOW,
    )
    ctx = Context(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        evidence_ids=[evidence.id],
        mental_model_id="resource_pressure",
        purpose="infrastructure_health",
        coherence_score=0.7,
        competing_models=[],
        activated_at=NOW,
        is_active=True,
    )
    pattern = Pattern(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        context_id=ctx.id,
        pattern_type="temporal",
        description="Regularidad detectada.",
        strength_measure=0.9,
        frequency="daily",
        detected_at=NOW,
        is_active=True,
    )
    anomaly = Anomaly(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        context_id=ctx.id,
        pattern_id=pattern.id,
        deviation_score=2.5,
        tolerance_threshold=1.0,
        anomaly_class="point",
        detected_at=NOW,
    )
    chain = make_chain()
    hypothesis = Hypothesis(
        **{
            **chain["hypothesis"].model_dump(),
            "anomaly_ids": [anomaly.id],
            "pattern_ids": [pattern.id],
        }
    )
    source = ReportSource(
        tenant={"id": TENANT, "name": "Sandbox Tenant", "slug": "sandbox"},
        decisions=(chain["decision"],),
        recommendations=(chain["recommendation"],),
        contexts=(ctx,),
        confidences=(chain["confidence"],),
        hypotheses=(hypothesis,),
        anomalies=(anomaly,),
        patterns=(pattern,),
        evidence=(evidence,),
        observations=(obs,),
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        generated_at=NOW,
    )
    trace = build_decision_traces(source)[0]
    assert trace["anomalies"][0]["id"] == str(anomaly.id)
    assert trace["anomalies"][0]["deviation_score"] == 2.5
    assert trace["patterns"][0]["id"] == str(pattern.id)
    assert trace["contexts"][0]["id"] == str(ctx.id)
    assert trace["evidence"][0]["id"] == str(evidence.id)
    assert trace["observations"][0]["id"] == str(obs["id"])
    assert trace["observations"][0]["fact_type"] == "disk_usage_percent"