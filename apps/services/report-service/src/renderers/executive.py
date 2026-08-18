"""Executive Summary renderer (pure, no I/O).

Renders the 1-page non-technical Executive Summary template (docs/04 FASE 6,
Executive Summary Template): Top N critical decisions with risk/confidence and
their falsifiable expected outcomes, the top future risks (hypotheses whose
calibrated Confidence exceeds a threshold) and the decisions that require
authority (in this MVP: the high-risk commitments, whose authority binds the
strongest confidence - docs/03 "> 0.9 for irreversible"; real users arrive in
the Auth sprint). The renderer ONLY formats what the canonical flow already
committed (ADR-0002): cost/ROI figures from the template are NOT invented - they
are omitted because no table carries them.
"""
from datetime import UTC, datetime

from src.renderers.common import ReportSource, confidence_view, latest_confidence_for


def render_executive(
    source: ReportSource,
    top_n: int = 3,
    risk_threshold: float = 0.6,
) -> dict:
    """Render the executive document from already-read pipeline data (pure)."""
    now = source.generated_at or datetime.now(UTC)
    confidences = {c.id: c for c in source.confidences}
    recommendations = {r.id: r for r in source.recommendations}

    ranked = sorted(
        source.decisions,
        key=lambda d: (
            confidences[d.confidence_id].confidence_score
            if d.confidence_id in confidences
            else 0.0,
            d.committed_at,
        ),
        reverse=True,
    )
    top_decisions = []
    for decision in ranked[:top_n]:
        confidence = confidences.get(decision.confidence_id)
        recommendation = recommendations.get(decision.recommendation_id)
        top_decisions.append(
            {
                "decision_id": str(decision.id),
                "commitment": decision.commitment,
                "risk_tolerance": decision.risk_tolerance,
                "confidence": (
                    confidence.confidence_score if confidence is not None else None
                ),
                "expected_outcome_count": len(decision.expected_outcomes),
                "action": (
                    recommendation.action_description
                    if recommendation is not None
                    else None
                ),
            }
        )

    future_risks = []
    for hypothesis in source.hypotheses:
        confidence = latest_confidence_for(
            source.confidences, "hypothesis", hypothesis.id
        )
        if confidence is not None and confidence.confidence_score > risk_threshold:
            future_risks.append(
                {
                    "hypothesis_id": str(hypothesis.id),
                    "description": hypothesis.description,
                    "confidence": confidence.confidence_score,
                    "status": hypothesis.status,
                }
            )
    future_risks.sort(key=lambda r: r["confidence"], reverse=True)
    future_risks = future_risks[:3]

    pending_authority = [
        {
            "decision_id": str(decision.id),
            "commitment": decision.commitment,
            "risk_tolerance": decision.risk_tolerance,
        }
        for decision in source.decisions
        if decision.risk_tolerance == "high"
    ]

    confidence_rows = [
        confidence_view(confidence) for confidence in source.confidences
    ]

    return {
        "report_type": "executive",
        "title": "COS-Monitor Executive Summary",
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
        "top_decisions": top_decisions,
        "future_risks": future_risks,
        "pending_authority": pending_authority,
        "confidence_scores": confidence_rows,
    }