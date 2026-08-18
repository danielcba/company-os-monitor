"""JSON data renderer (pure, no I/O).

Renders the same data the Technical report formats in a pure JSON structure
(no template sections, no prose): one trace per Decision plus the raw
pipeline artifacts (recommendations, contexts, confidence scores, hypotheses).
Consumed by the API / dashboards. Values are JSON-native; nothing is invented
(ADR-0002).
"""
from datetime import UTC, datetime

from src.renderers.common import (
    ReportSource,
    anomaly_view,
    build_decision_traces,
    confidence_view,
    context_view,
    evidence_view,
    hypothesis_view,
    pattern_view,
    recommendation_view,
)


def render_json(source: ReportSource) -> dict:
    """Render the pure JSON document from already-read pipeline data (pure)."""
    now = source.generated_at or datetime.now(UTC)
    return {
        "report_type": "json",
        "title": "COS-Monitor Data Report (JSON)",
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
        "decision_traces": build_decision_traces(source),
        "recommendations": [recommendation_view(r) for r in source.recommendations],
        "contexts": [context_view(c) for c in source.contexts],
        "confidence_scores": [confidence_view(c) for c in source.confidences],
        "hypotheses": [hypothesis_view(h) for h in source.hypotheses],
        "anomalies": [anomaly_view(a) for a in source.anomalies],
        "patterns": [pattern_view(p) for p in source.patterns],
        "evidence": [evidence_view(e) for e in source.evidence],
    }