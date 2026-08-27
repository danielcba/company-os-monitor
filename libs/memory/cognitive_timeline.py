"""Cognitive Timeline (Investigation, read/compute) — temporal reconstruction.

Reconstructs the chronological sequence of cognitive events for a tenant from
the canonical read stores: ``Observation -> Evidence -> Context -> Pattern ->
Anomaly -> Hypothesis -> Insight -> Recommendation -> Decision -> Report ->
Confidence``, plus the Episodic Memory (``audit_log``). It is read-only and
never fabricates events (P1). This mirrors the Cognitive Trace read model
(Fase 2A/2B): a reconstruction under demand, NOT a persisted entity and NOT a
new cognitive stage.

R1: single capability — reconstruct the cognitive timeline for a tenant.
P1: no fabrication — only events present in the canonical stores are shown.
ADR-0002: external read/compute capability; consumes gateway read stores only.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# --- Reader contracts (gateway read stores; one list method each) -----------


@runtime_checkable
class _ObservationReader(Protocol):
    async def list_observations(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _EvidenceReader(Protocol):
    async def list_evidence(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _ContextReader(Protocol):
    async def list_contexts(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _PatternReader(Protocol):
    async def list_patterns(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _AnomalyReader(Protocol):
    async def list_anomalies(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _HypothesisReader(Protocol):
    async def list_hypotheses(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _InsightReader(Protocol):
    async def list_insights(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _RecommendationReader(Protocol):
    async def list_recommendations(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _DecisionReader(Protocol):
    async def list_decisions(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _ReportReader(Protocol):
    async def list_reports(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _ConfidenceReader(Protocol):
    async def list_confidence(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class _AuditReader(Protocol):
    async def list_audit_logs(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class CognitiveTimelineStoreProtocol(Protocol):
    """Structural type for the Cognitive Timeline read model (read contract)."""

    async def build_for_tenant(
        self, *, tenant_id: uuid.UUID, limit_per_concept: int = 20, ascending: bool = False
    ) -> CognitiveTimelineReport:
        """Reconstruct the cognitive timeline for ``tenant_id``."""
        ...


@dataclass(frozen=True)
class TimelineEvent:
    """A single cognitive event in the tenant's timeline (read/compute)."""

    tenant_id: uuid.UUID
    layer: str
    concept: str
    id: str
    timestamp: str
    title: str
    detail: str
    target_type: str | None = None
    target_id: str | None = None
    status: str | None = None

    def to_payload(self) -> dict[str, str]:
        return {
            "tenant_id": str(self.tenant_id),
            "layer": self.layer,
            "concept": self.concept,
            "id": str(self.id),
            "timestamp": self.timestamp,
            "title": self.title,
            "detail": self.detail,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "status": self.status,
        }


@dataclass(frozen=True)
class CognitiveTimelineReport:
    """Tenant-scoped chronological reconstruction (read/compute, never persisted)."""

    tenant_id: uuid.UUID
    events: list[TimelineEvent] = field(default_factory=list)
    total: int = 0
    per_layer_counts: dict[str, int] = field(default_factory=dict)
    per_concept_counts: dict[str, int] = field(default_factory=dict)
    ascending: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "events": [e.to_payload() for e in self.events],
            "total": self.total,
            "per_layer_counts": self.per_layer_counts,
            "per_concept_counts": self.per_concept_counts,
            "ascending": self.ascending,
        }


def _short(value: Any, limit: int = 80) -> str:
    if value is None:
        return ""
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}..."


def _title_detail(concept: str, item: dict[str, Any]) -> tuple[str, str, str | None]:  # noqa: PLR0911
    """(title, detail, status) for a canonical payload of ``concept``."""
    if concept == "observation":
        detail = (
            f"{_short(item.get('fact_value'))} {item.get('unit', '')} "
            f"(quality={item.get('quality_class')})"
        ).strip()
        return (
            f"Observation: {item.get('fact_type', '?')}",
            detail,
            None,
        )
    if concept == "evidence":
        return (
            f"Evidence: {item.get('metric', '?')}",
            f"unit={item.get('unit')}, quality={item.get('quality_class')}",
            None,
        )
    if concept == "context":
        return (
            "Context activated",
            f"coherence={item.get('coherence_score')}, models={item.get('competing_models')}",
            None,
        )
    if concept == "pattern":
        return (
            f"Pattern: {item.get('pattern_type', '?')}",
            f"strength={item.get('strength_measure')}, frequency={item.get('frequency')}",
            None,
        )
    if concept == "anomaly":
        return (
            f"Anomaly: {item.get('anomaly_class', '?')}",
            f"deviation={item.get('deviation_score')} (tol={item.get('tolerance_threshold')})",
            None,
        )
    if concept == "hypothesis":
        status = item.get("status")
        return (
            f"Hypothesis ({status})",
            _short(item.get("statement") or item.get("rationale")),
            status,
        )
    if concept == "insight":
        return (
            "Insight",
            _short(item.get("mental_model_update") or item.get("prior_understanding")),
            None,
        )
    if concept == "recommendation":
        status = item.get("status")
        return (
            f"Recommendation ({status})",
            f"confidence={item.get('confidence_score')}",
            status,
        )
    if concept == "decision":
        status = item.get("status")
        return (
            f"Decision ({status})",
            f"risk={item.get('risk_tolerance')}",
            status,
        )
    if concept == "report":
        return (
            f"Report ({item.get('model_used', '?')})",
            f"{item.get('period_start')}..{item.get('period_end')}",
            None,
        )
    if concept == "confidence":
        return (
            f"Confidence: {item.get('target_type', '?')}",
            f"alpha={item.get('alpha')}, support={item.get('evidential_support')}",
            None,
        )
    if concept == "audit":
        return (
            f"{item.get('cognitive_concept', '?')} {item.get('action', '')}".strip(),
            f"layer={item.get('cognitive_layer')}",
            None,
        )
    return (concept, _short(item), None)


# Source descriptors: (concept, layer, reader_attr, method, response_key, ts_field)
_SOURCES: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("observation", "perception", "_observation_store", "list_observations",
     "observations", "captured_at"),
    ("evidence", "perception", "_evidence_store", "list_evidence", "evidence", "organized_at"),
    ("context", "perception", "_context_store", "list_contexts", "contexts", "activated_at"),
    ("pattern", "reasoning", "_pattern_store", "list_patterns", "patterns", "detected_at"),
    ("anomaly", "reasoning", "_anomaly_store", "list_anomalies", "anomalies", "detected_at"),
    ("hypothesis", "reasoning", "_hypothesis_store", "list_hypotheses",
     "hypotheses", "generated_at"),
    ("insight", "reasoning", "_insight_store", "list_insights", "insights", "generated_at"),
    ("recommendation", "action", "_recommendation_store", "list_recommendations",
     "recommendations", "proposed_at"),
    ("decision", "action", "_decision_store", "list_decisions", "decisions", "committed_at"),
    ("report", "memory", "_report_store", "list_reports", "reports", "generated_at"),
    ("confidence", "confidence", "_confidence_store", "list_confidence",
     "confidence", "computed_at"),
    ("audit", "memory", "_audit_store", "list_audit_logs", "entries", "timestamp"),
)


async def build_cognitive_timeline(  # noqa: PLR0913
    tenant_id: uuid.UUID,
    *,
    observation_store: _ObservationReader,
    evidence_store: _EvidenceReader,
    context_store: _ContextReader,
    pattern_store: _PatternReader,
    anomaly_store: _AnomalyReader,
    hypothesis_store: _HypothesisReader,
    insight_store: _InsightReader,
    recommendation_store: _RecommendationReader,
    decision_store: _DecisionReader,
    report_store: _ReportReader,
    confidence_store: _ConfidenceReader,
    audit_store: _AuditReader,
    limit_per_concept: int = 20,
    ascending: bool = False,
) -> CognitiveTimelineReport:
    """Reconstruct the chronological cognitive timeline (read/compute, no IO)."""
    readers = {
        "_observation_store": observation_store,
        "_evidence_store": evidence_store,
        "_context_store": context_store,
        "_pattern_store": pattern_store,
        "_anomaly_store": anomaly_store,
        "_hypothesis_store": hypothesis_store,
        "_insight_store": insight_store,
        "_recommendation_store": recommendation_store,
        "_decision_store": decision_store,
        "_report_store": report_store,
        "_confidence_store": confidence_store,
        "_audit_store": audit_store,
    }

    events: list[TimelineEvent] = []
    per_layer: dict[str, int] = {}
    per_concept: dict[str, int] = {}

    for concept, layer, reader_attr, method, response_key, ts_field in _SOURCES:
        reader = readers[reader_attr]
        if reader is None:
            continue
        try:
            payload = await getattr(reader, method)(tenant_id=tenant_id, limit=limit_per_concept)
        except Exception:  # noqa: BLE001 - a single unavailable source must not break the timeline
            continue
        items = payload.get(response_key, []) if isinstance(payload, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            ts = item.get(ts_field)
            if ts is None:
                continue
            title, detail, status = _title_detail(concept, item)
            events.append(
                TimelineEvent(
                    tenant_id=tenant_id,
                    layer=layer,
                    concept=concept,
                    id=str(item.get("id", "")),
                    timestamp=str(ts),
                    title=title,
                    detail=detail,
                    target_type=item.get("target_type"),
                    target_id=str(item["target_id"]) if item.get("target_id") is not None else None,
                    status=status,
                )
            )
            per_layer[layer] = per_layer.get(layer, 0) + 1
            per_concept[concept] = per_concept.get(concept, 0) + 1

    events.sort(key=lambda e: e.timestamp, reverse=not ascending)

    return CognitiveTimelineReport(
        tenant_id=tenant_id,
        events=events,
        total=len(events),
        per_layer_counts=per_layer,
        per_concept_counts=per_concept,
        ascending=ascending,
    )


class CognitiveTimelineStore:
    """Read/compute store: reconstructs a tenant's cognitive timeline on demand.

    Wraps the canonical gateway read stores across all cognitive layers and
    applies the pure temporal reconstruction. It performs NO writes and creates
    NO new entity (ADR-0002): the timeline is derived, never persisted.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        observation_store: _ObservationReader,
        evidence_store: _EvidenceReader,
        context_store: _ContextReader,
        pattern_store: _PatternReader,
        anomaly_store: _AnomalyReader,
        hypothesis_store: _HypothesisReader,
        insight_store: _InsightReader,
        recommendation_store: _RecommendationReader,
        decision_store: _DecisionReader,
        report_store: _ReportReader,
        confidence_store: _ConfidenceReader,
        audit_store: _AuditReader,
    ):
        self._observation_store = observation_store
        self._evidence_store = evidence_store
        self._context_store = context_store
        self._pattern_store = pattern_store
        self._anomaly_store = anomaly_store
        self._hypothesis_store = hypothesis_store
        self._insight_store = insight_store
        self._recommendation_store = recommendation_store
        self._decision_store = decision_store
        self._report_store = report_store
        self._confidence_store = confidence_store
        self._audit_store = audit_store

    async def build_for_tenant(
        self, *, tenant_id: uuid.UUID, limit_per_concept: int = 20, ascending: bool = False
    ) -> CognitiveTimelineReport:
        return await build_cognitive_timeline(
            tenant_id,
            observation_store=self._observation_store,
            evidence_store=self._evidence_store,
            context_store=self._context_store,
            pattern_store=self._pattern_store,
            anomaly_store=self._anomaly_store,
            hypothesis_store=self._hypothesis_store,
            insight_store=self._insight_store,
            recommendation_store=self._recommendation_store,
            decision_store=self._decision_store,
            report_store=self._report_store,
            confidence_store=self._confidence_store,
            audit_store=self._audit_store,
            limit_per_concept=limit_per_concept,
            ascending=ascending,
        )

    async def verify_connection(self) -> None:
        for store in (
            self._observation_store,
            self._evidence_store,
            self._context_store,
            self._pattern_store,
            self._anomaly_store,
            self._hypothesis_store,
            self._insight_store,
            self._recommendation_store,
            self._decision_store,
            self._report_store,
            self._confidence_store,
            self._audit_store,
        ):
            if hasattr(store, "verify_connection"):
                await store.verify_connection()

    async def close(self) -> None:
        for store in (
            self._observation_store,
            self._evidence_store,
            self._context_store,
            self._pattern_store,
            self._anomaly_store,
            self._hypothesis_store,
            self._insight_store,
            self._recommendation_store,
            self._decision_store,
            self._report_store,
            self._confidence_store,
            self._audit_store,
        ):
            if hasattr(store, "close"):
                await store.close()
