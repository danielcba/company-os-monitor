"""Technical Report renderer (pure, no I/O).

Renders the full cognitive trace template (docs/04 FASE 6, Technical Report
Template - Trazabilidad Cognitiva Completa) as SECTION 1..7 per Decision:
  SECTION 1 Cognitive Trace, SECTION 2 Evidence Chain, SECTION 3 Reasoning
  Chain, SECTION 4 Confidence Calibration, SECTION 5 Recommendation &
  Alternatives, SECTION 6 Decision & Expected Outcomes, SECTION 7 Learning Loop.

SECTION 7 is the post-execution comparison (expected vs actual, Brier/ECE
update) populated with learning loop data from outcome comparison.
Every value comes from the pipeline tables; the renderer formats, it never
invents (ADR-0002).
"""
from datetime import UTC, datetime

from libs.action.decision import compare_expected_actual_outcomes
from libs.cognitive_core.calibration_model import CalibrationParams

from src.renderers.common import ReportSource, build_decision_traces


def render_technical(source: ReportSource) -> dict:
    """Render the technical document from already-read pipeline data (pure)."""
    now = source.generated_at or datetime.now(UTC)
    traces = build_decision_traces(source)
    params = CalibrationParams()

    # Compute learning loop data (expected vs actual outcomes) per decision
    learning_loop_data = []
    for trace in traces:
        decision = trace["decision"]
        expected_outcomes = decision["expected_outcomes"]
        actual_outcomes = decision.get("actual_outcomes")
        if expected_outcomes:
            comparison = compare_expected_actual_outcomes(
                expected_outcomes, actual_outcomes, params
            )
        else:
            comparison = {
                "brier_score": 0.0,
                "ece": 0.0,
                "historical_calibration": 1.0,
                "confidence_adjustment": 0.0,
                "original_confidence": 0.0,
                "adjusted_confidence": 0.0,
                "outcome_count": 0,
                "details": [],
            }
        learning_loop_data.append(comparison)

    return {
        "report_type": "technical",
        "title": "COS-Monitor Technical Report - Cognitive Trace",
        "generated_at": now.isoformat(),
        "tenant": {
            "id": str(source.tenant["id"]),
            "name": source.tenant["name"],
            "slug": source.tenant.get("slug"),
        },
        "period": {
            "start": source.period_start.isoformat(),
            "end": source.period_end.isoformat(),
        },
        "decision_count": len(source.decisions),
        "section_1_cognitive_trace": [
            {
                "decision_id": trace["decision"]["id"],
                "commitment": trace["decision"]["commitment"],
                "authority_id": trace["decision"]["authority_id"],
                "risk_tolerance": trace["decision"]["risk_tolerance"],
                "status": trace["decision"]["status"],
                "committed_at": trace["decision"]["committed_at"],
                "confidence": (
                    trace["confidence"]["confidence_score"]
                    if trace["confidence"] is not None
                    else None
                ),
            }
            for trace in traces
        ],
        "section_2_evidence_chain": [
            {
                "decision_id": trace["decision"]["id"],
                "observations": trace["observations"],
                "evidence": trace["evidence"],
                "contexts": trace["contexts"],
            }
            for trace in traces
        ],
        "section_3_reasoning_chain": [
            {
                "decision_id": trace["decision"]["id"],
                "hypothesis": trace["hypothesis"],
                "anomalies": trace["anomalies"],
                "patterns": trace["patterns"],
            }
            for trace in traces
        ],
        "section_4_confidence_calibration": [
            {
                "decision_id": trace["decision"]["id"],
                "confidence": trace["confidence"],
            }
            for trace in traces
        ],
        "section_5_recommendation_and_alternatives": [
            {
                "decision_id": trace["decision"]["id"],
                "recommendation": trace["recommendation"],
            }
            for trace in traces
        ],
        "section_6_decision_and_expected_outcomes": [
            {
                "decision_id": trace["decision"]["id"],
                "commitment": trace["decision"]["commitment"],
                "expected_outcomes": trace["decision"]["expected_outcomes"],
                "actual_outcomes": trace["decision"].get("actual_outcomes"),
            }
            for trace in traces
        ],
        "section_7_learning_loop": learning_loop_data,
    }