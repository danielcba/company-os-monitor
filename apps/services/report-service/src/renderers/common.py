"""Pure shared helpers for the report renderers (no I/O, no DB access).

The renderers receive the data ALREADY READ from the cognitive tables (the
orchestrator reads, the renderer formats - single responsibility). Everything
here is a pure function over that data: JSON-safe views of the models and the
full cognitive trace assembly for one Decision.
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


def as_jsonable(value: Any) -> Any:
    """Recursively convert a value into JSON-native types (uuid -> str, datetime -> iso)."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: as_jsonable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_jsonable(val) for val in value]
    return str(value)


@dataclass(frozen=True)
class ReportSource:
    """The data bundle a renderer formats (built by the orchestrator, READ-only).

    Every field is data already loaded from the cognitive tables (P1: the
    renderers never touch the database). ``tenant`` is the support ``tenants``
    row (id/name/slug); the remaining fields are the pipeline artifacts the
    report formats; ``period_start``/``period_end`` delimit the report window;
    ``generated_at`` anchors the generation instant (injected for determinism).
    """

    tenant: dict[str, Any]
    decisions: tuple[Any, ...]
    recommendations: tuple[Any, ...]
    contexts: tuple[Any, ...]
    confidences: tuple[Any, ...]
    hypotheses: tuple[Any, ...]
    anomalies: tuple[Any, ...]
    patterns: tuple[Any, ...]
    evidence: tuple[Any, ...]
    observations: tuple[Any, ...]
    period_start: date
    period_end: date
    generated_at: datetime


def by_id(records: tuple[Any, ...]) -> dict:
    """Index a record stream by its ``id`` field."""
    return {record.id: record for record in records}


def latest_confidence_for(
    confidences: tuple[Any, ...], target_type: str, target_id: uuid.UUID
) -> Any | None:
    """The most recent calibration row for a target (append-only history).

    A target may have several calibration rows (each a distinct input set); the
    report uses the LATEST one by ``computed_at`` - the one the flow currently
    relies on.
    """
    matches = [
        c
        for c in confidences
        if c.target_type == target_type and c.target_id == target_id
    ]
    if not matches:
        return None
    return max(matches, key=lambda c: c.computed_at)


def decision_view(decision: Any) -> dict[str, Any]:
    return {
        "id": str(decision.id),
        "commitment": decision.commitment,
        "risk_tolerance": decision.risk_tolerance,
        "status": decision.status,
        "committed_at": decision.committed_at.isoformat(),
        "authority_id": str(decision.authority_id),
        "expected_outcomes": as_jsonable(decision.expected_outcomes),
        "actual_outcomes": as_jsonable(decision.actual_outcomes),
    }


def confidence_view(confidence: Any) -> dict[str, Any]:
    return {
        "id": str(confidence.id),
        "target_type": confidence.target_type,
        "target_id": str(confidence.target_id),
        "evidential_support": confidence.evidential_support,
        "explanatory_coherence": confidence.explanatory_coherence,
        "historical_calibration": confidence.historical_calibration,
        "confidence_score": confidence.confidence_score,
        "alpha": confidence.alpha,
        "calibration_justification": confidence.calibration_justification,
        "calibration_error_estimate": confidence.calibration_error_estimate,
        "computed_at": confidence.computed_at.isoformat(),
    }


def recommendation_view(recommendation: Any) -> dict[str, Any]:
    return {
        "id": str(recommendation.id),
        "hypothesis_id": str(recommendation.hypothesis_id),
        "action_description": recommendation.action_description,
        "rationale": recommendation.rationale,
        "expected_consequences": as_jsonable(recommendation.expected_consequences),
        "alternatives_considered": as_jsonable(recommendation.alternatives_considered),
        "confidence_score": recommendation.confidence_score,
        "status": recommendation.status,
        "proposed_at": recommendation.proposed_at.isoformat(),
    }


def hypothesis_view(hypothesis: Any) -> dict[str, Any]:
    return {
        "id": str(hypothesis.id),
        "anomaly_ids": [str(aid) for aid in hypothesis.anomaly_ids],
        "pattern_ids": [str(pid) for pid in hypothesis.pattern_ids],
        "description": hypothesis.description,
        "predicted_consequences": as_jsonable(hypothesis.predicted_consequences),
        "falsification_criterion": hypothesis.falsification_criterion,
        "coherence_score": hypothesis.coherence_score,
        "status": hypothesis.status,
        "generated_at": hypothesis.generated_at.isoformat(),
    }


def anomaly_view(anomaly: Any) -> dict[str, Any]:
    return {
        "id": str(anomaly.id),
        "context_id": str(anomaly.context_id),
        "pattern_id": str(anomaly.pattern_id),
        "deviation_score": anomaly.deviation_score,
        "tolerance_threshold": anomaly.tolerance_threshold,
        "anomaly_class": anomaly.anomaly_class,
        "detected_at": anomaly.detected_at.isoformat(),
    }


def pattern_view(pattern: Any) -> dict[str, Any]:
    return {
        "id": str(pattern.id),
        "context_id": str(pattern.context_id),
        "pattern_type": pattern.pattern_type,
        "description": pattern.description,
        "strength_measure": pattern.strength_measure,
        "frequency": pattern.frequency,
        "is_active": pattern.is_active,
        "detected_at": pattern.detected_at.isoformat(),
    }


def context_view(context: Any) -> dict[str, Any]:
    return {
        "id": str(context.id),
        "evidence_ids": [str(eid) for eid in context.evidence_ids],
        "mental_model_id": context.mental_model_id,
        "purpose": context.purpose,
        "coherence_score": context.coherence_score,
        "competing_models": as_jsonable(context.competing_models),
        "is_active": context.is_active,
        "activated_at": context.activated_at.isoformat(),
    }


def evidence_view(evidence: Any) -> dict[str, Any]:
    return {
        "id": str(evidence.id),
        "observation_ids": [str(oid) for oid in evidence.observation_ids],
        "organization_type": evidence.organization_type,
        "description": evidence.description,
        "quality_class": (
            evidence.quality_class.value
            if hasattr(evidence.quality_class, "value")
            else str(evidence.quality_class)
        ),
        "weight": evidence.weight,
        "organized_at": evidence.organized_at.isoformat(),
    }


def observation_view(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(observation["id"]),
        "fact_type": observation["fact_type"],
        "fact_value": as_jsonable(observation["fact_value"]),
        "unit": observation["unit"],
        "captured_at": observation["captured_at"].isoformat()
        if isinstance(observation["captured_at"], datetime)
        else str(observation["captured_at"]),
        "quality_class": str(observation["quality_class"]),
    }


def build_decision_traces(source: ReportSource) -> list[dict[str, Any]]:
    """Assemble the full cognitive trace of the Decisions (pure, JSON-safe).

    For every Decision correlates decision -> confidence
    (``decision.confidence_id``) and decision -> recommendation
    (``decision.recommendation_id``) -> hypothesis -> anomalies/patterns ->
    contexts (``anomaly.context_id``) -> evidence (``context.evidence_ids``) ->
    observations (``evidence.observation_ids``). Only data that EXISTS in the
    pipeline tables is included; the report never invents judgments (ADR-0002).
    Returns one trace dict per Decision.
    """
    trace = []
    confidences = by_id(source.confidences)
    recommendations = by_id(source.recommendations)
    hypotheses = by_id(source.hypotheses)
    anomalies = by_id(source.anomalies)
    patterns = by_id(source.patterns)
    contexts = by_id(source.contexts)
    evidence = by_id(source.evidence)
    observations = {obs["id"]: obs for obs in source.observations}

    for decision in source.decisions:
        confidence = confidences.get(decision.confidence_id)
        recommendation = recommendations.get(decision.recommendation_id)
        hypothesis = (
            hypotheses.get(recommendation.hypothesis_id)
            if recommendation is not None
            else None
        )
        anomaly_list = []
        pattern_list = []
        context_list = []
        evidence_list = []
        observation_list = []
        if hypothesis is not None:
            for anomaly_id in hypothesis.anomaly_ids:
                anomaly = anomalies.get(anomaly_id)
                if anomaly is None:
                    continue
                anomaly_list.append(anomaly_view(anomaly))
                pattern = patterns.get(anomaly.pattern_id)
                if pattern is not None:
                    pattern_list.append(pattern_view(pattern))
                ctx = contexts.get(anomaly.context_id)
                if ctx is not None:
                    context_list.append(context_view(ctx))
                    for evidence_id in ctx.evidence_ids:
                        ev = evidence.get(evidence_id)
                        if ev is None:
                            continue
                        evidence_list.append(evidence_view(ev))
                        for obs_id in ev.observation_ids:
                            obs = observations.get(obs_id)
                            if obs is not None:
                                observation_list.append(observation_view(obs))
        trace.append(
            {
                "decision": decision_view(decision) if decision is not None else None,
                "confidence": (
                    confidence_view(confidence) if confidence is not None else None
                ),
                "recommendation": (
                    recommendation_view(recommendation)
                    if recommendation is not None
                    else None
                ),
                "hypothesis": (
                    hypothesis_view(hypothesis) if hypothesis is not None else None
                ),
                "anomalies": anomaly_list,
                "patterns": pattern_list,
                "contexts": context_list,
                "evidence": evidence_list,
                "observations": observation_list,
            }
        )
    return trace