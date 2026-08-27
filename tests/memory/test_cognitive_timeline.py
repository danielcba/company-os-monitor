"""Unit tests for the Cognitive Timeline reconstruction (pure read/compute).

No IO: exercises event mapping, temporal sorting, layer/concept counting and
the defensive skip of an unavailable reader, using fake readers that implement
the gateway read-store contract (return a dict payload with a known key).
"""
import types
import uuid

from libs.memory.cognitive_timeline import (
    CognitiveTimelineStore,
    build_cognitive_timeline,
)


def _reader(method_name: str, key: str, items: list[dict]) -> object:
    async def meth(*, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
        return {key: items}

    return types.SimpleNamespace(**{method_name: meth})


_T = "2026-01-01T00:00:00"
_READERS = {
    "observation": ("list_observations", "observations", [
        {"id": "o1", "fact_type": "cpu", "fact_value": 90, "unit": "%",
         "quality_class": "high", "captured_at": f"{_T}"},
    ]),
    "evidence": ("list_evidence", "evidence", [
        {"id": "e1", "metric": "latency", "unit": "ms",
         "quality_class": "high", "organized_at": f"{_T}"},
    ]),
    "context": ("list_contexts", "contexts", [
        {"id": "c1", "coherence_score": 0.8, "competing_models": 3,
         "activated_at": f"{_T}"},
    ]),
    "pattern": ("list_patterns", "patterns", [
        {"id": "p1", "pattern_type": "seasonal", "strength_measure": 0.9,
         "frequency": 5, "detected_at": f"{_T}"},
    ]),
    "anomaly": ("list_anomalies", "anomalies", [
        {"id": "a1", "anomaly_class": "spike", "deviation_score": 2.1,
         "tolerance_threshold": 1.5, "detected_at": f"{_T}"},
    ]),
    "hypothesis": ("list_hypotheses", "hypotheses", [
        {"id": "h1", "status": "candidate", "statement": "cpu will rise",
         "generated_at": f"{_T}"},
    ]),
    "insight": ("list_insights", "insights", [
        {"id": "i1", "mental_model_update": "model updated",
         "generated_at": f"{_T}"},
    ]),
    "recommendation": ("list_recommendations", "recommendations", [
        {"id": "r1", "status": "proposed", "confidence_score": 0.7,
         "proposed_at": f"{_T}"},
    ]),
    "decision": ("list_decisions", "decisions", [
        {"id": "d1", "status": "committed", "risk_tolerance": "low",
         "committed_at": f"{_T}"},
    ]),
    "report": ("list_reports", "reports", [
        {"id": "rep1", "model_used": "gpt", "period_start": "2026-01-01",
         "period_end": "2026-01-02", "generated_at": f"{_T}"},
    ]),
    "confidence": ("list_confidence", "confidence", [
        {"id": "cf1", "target_type": "decision", "target_id": "d1",
         "alpha": 0.1, "evidential_support": 0.8, "computed_at": f"{_T}"},
    ]),
    "audit": ("list_audit_logs", "entries", [
        {"id": "au1", "cognitive_concept": "observation", "action": "captured",
         "cognitive_layer": "perception", "timestamp": f"{_T}"},
    ]),
}


def _build_readers():
    return {
        name: _reader(method, key, items)
        for name, (method, key, items) in _READERS.items()
    }


EXPECTED_TOTAL = len(_READERS)


async def test_build_cognitive_timeline_maps_and_counts():
    tenant = uuid.uuid4()
    readers = _build_readers()
    report = await build_cognitive_timeline(
        tenant,
        observation_store=readers["observation"],
        evidence_store=readers["evidence"],
        context_store=readers["context"],
        pattern_store=readers["pattern"],
        anomaly_store=readers["anomaly"],
        hypothesis_store=readers["hypothesis"],
        insight_store=readers["insight"],
        recommendation_store=readers["recommendation"],
        decision_store=readers["decision"],
        report_store=readers["report"],
        confidence_store=readers["confidence"],
        audit_store=readers["audit"],
    )
    assert report.total == EXPECTED_TOTAL
    assert report.per_concept_counts == dict.fromkeys(_READERS, 1)
    assert report.per_layer_counts == {
        "perception": 3, "reasoning": 4, "action": 2, "memory": 2, "confidence": 1,
    }


async def test_build_cognitive_timeline_sorts_descending_by_default():
    tenant = uuid.uuid4()
    # Give two events distinct timestamps via different readers.
    obs = _reader("list_observations", "observations", [
        {"id": "o1", "fact_type": "cpu", "fact_value": 1, "unit": "%",
         "quality_class": "high", "captured_at": "2026-01-01T00:00:00"},
    ])
    dec = _reader("list_decisions", "decisions", [
        {"id": "d1", "status": "committed", "risk_tolerance": "low",
         "committed_at": "2026-01-02T00:00:00"},
    ])
    report = await build_cognitive_timeline(
        tenant, observation_store=obs, evidence_store=obs, context_store=obs,
        pattern_store=obs, anomaly_store=obs, hypothesis_store=obs,
        insight_store=obs, recommendation_store=obs, decision_store=dec,
        report_store=obs, confidence_store=obs, audit_store=obs,
    )
    assert report.events[0].concept == "decision"  # newest first by default

    report_asc = await build_cognitive_timeline(
        tenant, observation_store=obs, evidence_store=obs, context_store=obs,
        pattern_store=obs, anomaly_store=obs, hypothesis_store=obs,
        insight_store=obs, recommendation_store=obs, decision_store=dec,
        report_store=obs, confidence_store=obs, audit_store=obs, ascending=True,
    )
    assert report_asc.events[0].concept == "observation"  # oldest first


async def test_build_cognitive_timeline_skips_unavailable_reader():
    tenant = uuid.uuid4()

    class _Boom:
        async def list_observations(self, *, tenant_id, limit=50, offset=0):
            raise RuntimeError

    # Only observation reader is broken; the rest are fine.
    readers = _build_readers()
    readers["observation"] = _Boom()
    report = await build_cognitive_timeline(
        tenant,
        observation_store=readers["observation"],
        evidence_store=readers["evidence"],
        context_store=readers["context"],
        pattern_store=readers["pattern"],
        anomaly_store=readers["anomaly"],
        hypothesis_store=readers["hypothesis"],
        insight_store=readers["insight"],
        recommendation_store=readers["recommendation"],
        decision_store=readers["decision"],
        report_store=readers["report"],
        confidence_store=readers["confidence"],
        audit_store=readers["audit"],
    )
    # Observation omitted (reader raised); the other (EXPECTED_TOTAL - 1) remain.
    assert report.total == EXPECTED_TOTAL - 1
    assert "observation" not in report.per_concept_counts


async def test_store_wraps_build_for_tenant():
    tenant = uuid.uuid4()
    store = CognitiveTimelineStore(
        observation_store=_reader("list_observations", "observations", []),
        evidence_store=_reader("list_evidence", "evidence", []),
        context_store=_reader("list_contexts", "contexts", []),
        pattern_store=_reader("list_patterns", "patterns", []),
        anomaly_store=_reader("list_anomalies", "anomalies", []),
        hypothesis_store=_reader("list_hypotheses", "hypotheses", []),
        insight_store=_reader("list_insights", "insights", []),
        recommendation_store=_reader("list_recommendations", "recommendations", []),
        decision_store=_reader("list_decisions", "decisions", []),
        report_store=_reader("list_reports", "reports", []),
        confidence_store=_reader("list_confidence", "confidence", []),
        audit_store=_reader("list_audit_logs", "entries", []),
    )
    report = await store.build_for_tenant(tenant_id=tenant)
    assert isinstance(report.total, int)
    assert report.tenant_id == tenant
