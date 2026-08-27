"""Insight Transformation journaling (R6) — read/compute.

The framework (R6): "Insight restructures existing knowledge — it journals the
transformation from a prior understanding to a new mental-model update." Each
Insight is, by construction, a recorded transformation (``prior_understanding``
-> ``mental_model_update``). This capability surfaces those transformations for
review and, when the outcome readers are available, attributes Decision outcome
verdicts back to the Insight that informed the Recommendation (traceability
Decision -> Recommendation[insight_id] -> Insight).

This module is a READ/COMPUTE capability (ADR-0002): it journals/summarizes
Insight transformations; it does NOT mutate canonical entities. Placement under
``libs.memory`` (NOT the reasoning package) keeps the gateway boundary clean: the
gateway consumes the read stores (dict payloads) and never imports the reasoning
pipeline.

R6: surfaces the prior -> updated mental-model transformation (the journal).
P4: classification is descriptive only (prior != updated); it never invents a
    causal explanation for the transformation.
P1: no fabrication — missing/inconclusive outcomes are never counted as failures.
R1: single capability — compute Insight transformation journaling from Insights.
ADR-0002: external read/compute capability; no new persisted entity.
"""
from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from libs.memory.consolidation import build_consolidation
from libs.memory.pattern_refinement import _DecisionView


class InsightTransformationResult(BaseModel):
    """One Insight's journaled transformation (read/compute; never persisted)."""

    insight_id: uuid.UUID
    tenant_id: uuid.UUID
    context_id: uuid.UUID | None
    description: str
    prior_understanding: str | None
    mental_model_update: dict[str, Any] | None
    transformation_kind: str  # "revised" | "stable" | "unchanged"
    linked_recommendations: int
    linked_decisions_with_outcomes: int
    corroborated: int
    contradicted: int
    inconclusive: int

    model_config = ConfigDict(frozen=True)


class InsightTransformationReport(BaseModel):
    """Tenant-scoped aggregate of Insight transformations (read/compute)."""

    tenant_id: uuid.UUID
    total_insights: int
    results: list[InsightTransformationResult] = []

    model_config = ConfigDict(frozen=True)


@runtime_checkable
class InsightReader(Protocol):
    async def list_insights(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class InsightDecisionReader(Protocol):
    async def list_decisions(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class InsightRecommendationReader(Protocol):
    async def list_recommendations(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class InsightTransformationStoreProtocol(Protocol):
    """Structural type for the Insight Transformation read model (read contract)."""

    async def journal_for_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> InsightTransformationReport:
        """Build the Insight Transformation journal for ``tenant_id``."""
        ...


def _classify_transformation(
    prior: str | None, updated: dict[str, Any] | None
) -> str:
    """Descriptive classification of the transformation (P4: no causal claim)."""
    prior_blank = prior is None or prior == ""
    updated_blank = updated is None or (isinstance(updated, dict) and not updated)
    if prior_blank and updated_blank:
        return "unchanged"
    if prior_blank or updated_blank:
        return "revised"
    # Compare serialized forms: any difference means the understanding changed.
    if str(prior).strip() != str(updated).strip():
        return "revised"
    return "stable"


def _attribute_outcomes_to_insights(
    decisions: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Attribute Decision outcome counts to Insights via recommendation.insight_id.

    Returns ``{insight_id_str: {corroborated, contradicted, inconclusive, linked,
    decisions_with_outcomes}}``. Defensive: missing recommendations/links are
    skipped.
    """
    rec_by_id = {r["id"]: r for r in recommendations}
    attribution: dict[str, dict[str, int]] = {}

    for decision in decisions:
        if not decision.get("actual_outcomes"):
            continue
        consolidation = build_consolidation(_DecisionView(decision))
        rec = rec_by_id.get(decision.get("recommendation_id"))
        if rec is None:
            continue
        insight_id_str = rec.get("insight_id")
        if insight_id_str is None:
            continue
        attr = attribution.setdefault(
            insight_id_str,
            {
                "corroborated": 0,
                "contradicted": 0,
                "inconclusive": 0,
                "linked": 0,
                "decisions_with_outcomes": 0,
            },
        )
        attr["corroborated"] += consolidation.corroborated
        attr["contradicted"] += consolidation.contradicted
        attr["inconclusive"] += consolidation.inconclusive
        attr["linked"] += 1
        attr["decisions_with_outcomes"] += 1

    return attribution


def _journal_insight(
    insight: dict[str, Any],
    *,
    linked_recommendations: int,
    attr: dict[str, int] | None,
) -> InsightTransformationResult:
    """Build one Insight transformation record (pure, no IO)."""
    transformation_kind = _classify_transformation(
        insight.get("prior_understanding"),
        insight.get("mental_model_update"),
    )
    if attr is None:
        corr = contr = incon = linked_outcomes = 0
    else:
        corr = attr["corroborated"]
        contr = attr["contradicted"]
        incon = attr["inconclusive"]
        linked_outcomes = attr["decisions_with_outcomes"]
    return InsightTransformationResult(
        insight_id=uuid.UUID(insight["id"]),
        tenant_id=uuid.UUID(insight["tenant_id"]),
        context_id=(
            uuid.UUID(insight["context_id"]) if insight.get("context_id") else None
        ),
        description=insight.get("description") or "",
        prior_understanding=insight.get("prior_understanding"),
        mental_model_update=insight.get("mental_model_update"),
        transformation_kind=transformation_kind,
        linked_recommendations=linked_recommendations,
        linked_decisions_with_outcomes=linked_outcomes,
        corroborated=corr,
        contradicted=contr,
        inconclusive=incon,
    )


async def build_insight_transformation(
    tenant_id: uuid.UUID,
    *,
    insight_reader: InsightReader,
    decision_reader: InsightDecisionReader | None = None,
    recommendation_reader: InsightRecommendationReader | None = None,
) -> InsightTransformationReport:
    """Build the tenant-scoped Insight Transformation journal (read/compute).

    The capability never imports the reasoning/perception pipeline packages
    (ADR-0002 boundary); it only consumes the canonical read contract. If the
    outcome readers are supplied, Decision verdicts are attributed to Insights
    via ``recommendation.insight_id``.
    """
    insights_payload = await insight_reader.list_insights(tenant_id=tenant_id)
    insights = insights_payload.get("insights", [])

    # Optional outcome attribution (traceability Decision -> Rec[insight] -> Insight).
    attribution: dict[str, dict[str, int]] | None = None
    rec_count_by_insight: dict[str, int] = {}
    if decision_reader is not None and recommendation_reader is not None:
        decisions_payload = await decision_reader.list_decisions(tenant_id=tenant_id)
        recommendations_payload = await recommendation_reader.list_recommendations(
            tenant_id=tenant_id
        )
        decisions = decisions_payload.get("decisions", [])
        recommendations = recommendations_payload.get("recommendations", [])
        attribution = _attribute_outcomes_to_insights(decisions, recommendations)
        # Count recommendations linked to each insight.
        for rec in recommendations:
            ins_id = rec.get("insight_id")
            if ins_id is not None:
                rec_count_by_insight[ins_id] = rec_count_by_insight.get(ins_id, 0) + 1

    results = []
    for insight in insights:
        attr = attribution.get(insight["id"]) if attribution is not None else None
        linked = rec_count_by_insight.get(insight["id"], 0)
        results.append(
            _journal_insight(
                insight, linked_recommendations=linked, attr=attr
            )
        )

    return InsightTransformationReport(
        tenant_id=tenant_id,
        total_insights=len(insights),
        results=results,
    )


class InsightTransformationStore:
    """Read/compute store: journals a tenant's Insight transformations on demand.

    Wraps the canonical gateway read stores (Insight, and optionally
    Decision/Recommendation for outcome attribution) and applies the pure
    journaling transform. It performs NO writes and creates NO new entity (Memory
    persistence remains planned per the framework).
    """

    def __init__(
        self,
        insight_store: InsightReader,
        decision_store: InsightDecisionReader | None = None,
        recommendation_store: InsightRecommendationReader | None = None,
    ):
        self._insight_store = insight_store
        self._decision_store = decision_store
        self._recommendation_store = recommendation_store

    async def journal_for_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> InsightTransformationReport:
        return await build_insight_transformation(
            tenant_id,
            insight_reader=self._insight_store,
            decision_reader=self._decision_store,
            recommendation_reader=self._recommendation_store,
        )

    async def verify_connection(self) -> None:
        if hasattr(self._insight_store, "verify_connection"):
            await self._insight_store.verify_connection()
