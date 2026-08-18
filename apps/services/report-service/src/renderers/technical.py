"""Technical Report renderer (pure, no I/O).

Renders the full cognitive trace template (docs/04 FASE 6, Technical Report
Template - Trazabilidad Cognitiva Completa) as SECTION 1..7 per Decision:
  SECTION 1 Cognitive Trace, SECTION 2 Evidence Chain, SECTION 3 Reasoning
  Chain, SECTION 4 Confidence Calibration, SECTION 5 Recommendation &
  Alternatives, SECTION 6 Decision & Expected Outcomes, SECTION 7 Learning Loop.
SECTION 7 is the post-execution comparison (expected vs actual, Brier/ECE
update) - a future phase, so it stays empty in this MVP. Every value comes from
the pipeline tables; the renderer formats, it never invents (ADR-0002).
"""
from datetime import UTC, datetime

from src.renderers.common import ReportSource, build_decision_traces


def render_technical(source: ReportSource) -> dict:
    """Render the technical document from already-read pipeline data (pure)."""
    now = source.generated_at or datetime.now(UTC)
    traces = build_decision_traces(source)

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
                "actual_outcomes": trace["decision"]["actual_outcomes"],
            }
            for trace in traces
        ],
        "section_7_learning_loop": [],
    }