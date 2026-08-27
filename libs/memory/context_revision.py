"""Context Revision (P7 + P2) — Learning Loop extension (read/compute).

The framework (P7): outcomes of committed Decisions feed back to revise the
context that framed them. The framework (P2): Context is activated by
coherence competition and is NEVER generated directly; revision is therefore a
*read/compute signal* that surfaces when a Context's Patterns produced
contradicted outcomes, and which competing model(s) could be reconsidered.

This module is a READ/COMPUTE capability (ADR-0002): it attributes Decision
outcomes to the Contexts that framed them (via the traceability chain
``Decision -> Recommendation -> Hypothesis -> Pattern -> Context``) and computes
a revision signal for each Context. It does NOT mutate canonical entities — the
signal is surfaced for review/action. Placement under ``libs.memory`` (NOT
the perception package) keeps the gateway boundary clean: the gateway consumes
the read stores (dict payloads) and never imports the perception pipeline.

P2: revision only *suggests* reconsidering a competing model; it never activates
    or generates a Context.
P7: contexts are revised from observed Decision outcomes.
P1: no fabrication — missing/inconclusive outcomes are never counted as failures.
R1: single capability — compute Context revision from outcomes.
ADR-0002: external read/compute capability; no new persisted entity.
"""
from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from libs.memory.consolidation import build_consolidation
from libs.memory.pattern_refinement import _DecisionView

# Minimum number of linked Decisions with outcomes before a Context can be
# recommended for revision (avoids over-reacting to noise).
MIN_SAMPLES_FOR_REVISION = 2
# Contradiction ratio above which a Context is recommended for revision.
REVISION_THRESHOLD = 0.5


class ContextRevisionResult(BaseModel):
    """Per-Context revision signal (read/compute; never persisted)."""

    context_id: uuid.UUID
    tenant_id: uuid.UUID
    linked_decisions: int
    corroborated: int
    contradicted: int
    inconclusive: int
    contradiction_ratio: float
    has_competing_models: bool
    recommended_revision: str  # "keep" | "review" | "consider_competitor"
    suggested_competitor: str | None

    model_config = ConfigDict(frozen=True)


class ContextRevisionReport(BaseModel):
    """Tenant-scoped aggregate of Context revision signals (read/compute)."""

    tenant_id: uuid.UUID
    total_contexts: int
    contexts_with_outcomes: int
    results: list[ContextRevisionResult] = []

    model_config = ConfigDict(frozen=True)


@runtime_checkable
class ContextRevisionStoreProtocol(Protocol):
    """Structural type for the Context Revision read model (read contract)."""

    async def revise_for_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> ContextRevisionReport:
        """Build the Context Revision signal for ``tenant_id``."""
        ...


def _attribute_outcomes_to_contexts(
    decisions: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Attribute Decision outcome counts to Contexts via the traceability chain.

    Returns ``{context_id_str: {corroborated, contradicted, inconclusive, linked}}``.
    The chain is ``Decision.recommendation_id -> Recommendation.hypothesis_id ->
    Hypothesis.pattern_ids -> Pattern.context_id -> Context``. Missing links are
    skipped (defensive). A Decision may map to several Contexts (multiple
    Patterns per Hypothesis), and each Context accumulates the outcome verdict.
    """
    rec_by_id = {r["id"]: r for r in recommendations}
    hyp_by_id = {h["id"]: h for h in hypotheses}
    pat_by_id = {p["id"]: p for p in patterns}

    attribution: dict[str, dict[str, int]] = {}

    for decision in decisions:
        if not decision.get("actual_outcomes"):
            continue
        consolidation = build_consolidation(_DecisionView(decision))
        corr = consolidation.corroborated
        contr = consolidation.contradicted
        incon = consolidation.inconclusive

        rec = rec_by_id.get(decision.get("recommendation_id"))
        if rec is None:
            continue
        hyp = hyp_by_id.get(rec.get("hypothesis_id"))
        if hyp is None:
            continue
        for pattern_id_str in hyp.get("pattern_ids") or []:
            pattern = pat_by_id.get(pattern_id_str)
            if pattern is None:
                continue
            context_id_str = pattern.get("context_id")
            if context_id_str is None:
                continue
            attr = attribution.setdefault(
                context_id_str,
                {"corroborated": 0, "contradicted": 0, "inconclusive": 0, "linked": 0},
            )
            attr["corroborated"] += corr
            attr["contradicted"] += contr
            attr["inconclusive"] += incon
            attr["linked"] += 1

    return attribution


def _revise_context(
    context: dict[str, Any], attr: dict[str, int]
) -> ContextRevisionResult:
    """Compute the revision signal for one Context (pure, no IO)."""
    corroborated = attr["corroborated"]
    contradicted = attr["contradicted"]
    inconclusive = attr["inconclusive"]
    linked = attr["linked"]
    total = corroborated + contradicted

    contradiction_ratio = (contradicted / total) if total > 0 else 0.0

    competing = context.get("competing_models") or []
    has_competing = bool(competing)

    if total < MIN_SAMPLES_FOR_REVISION or contradicted == 0:
        revision = "keep"
        suggested = None
    elif contradiction_ratio >= REVISION_THRESHOLD and has_competing:
        revision = "consider_competitor"
        suggested = _first_competitor_id(competing)
    elif contradiction_ratio >= REVISION_THRESHOLD:
        revision = "review"
        suggested = None
    else:
        revision = "review"
        suggested = None

    return ContextRevisionResult(
        context_id=uuid.UUID(context["id"]),
        tenant_id=uuid.UUID(context["tenant_id"]),
        linked_decisions=linked,
        corroborated=corroborated,
        contradicted=contradicted,
        inconclusive=inconclusive,
        contradiction_ratio=round(contradiction_ratio, 4),
        has_competing_models=has_competing,
        recommended_revision=revision,
        suggested_competitor=suggested,
    )


def _first_competitor_id(competing: list[dict[str, Any]]) -> str | None:
    """Pick the first competing model as the one to reconsider (P2: never
    auto-activates; only surfaces it for human review)."""
    if not competing:
        return None
    first = competing[0]
    return str(first.get("model_id") or first.get("name") or "")


async def build_context_revision(  # noqa: PLR0913
    tenant_id: uuid.UUID,
    *,
    decision_reader: Any,
    recommendation_reader: Any,
    hypothesis_reader: Any,
    pattern_reader: Any,
    context_reader: Any,
) -> ContextRevisionReport:
    """Build the tenant-scoped Context Revision report (read/compute, no IO).

    Each reader is the gateway's read store, whose ``list_*`` returns a
    paginated dict payload. The capability never imports the reasoning/
    perception pipeline packages (ADR-0002 boundary); it only consumes the
    canonical read contract.
    """
    decisions_payload = await decision_reader.list_decisions(tenant_id=tenant_id)
    recommendations_payload = await recommendation_reader.list_recommendations(
        tenant_id=tenant_id
    )
    hypotheses_payload = await hypothesis_reader.list_hypotheses(tenant_id=tenant_id)
    patterns_payload = await pattern_reader.list_patterns(tenant_id=tenant_id)
    contexts_payload = await context_reader.list_contexts(tenant_id=tenant_id)

    decisions = decisions_payload.get("decisions", [])
    recommendations = recommendations_payload.get("recommendations", [])
    hypotheses = hypotheses_payload.get("hypotheses", [])
    patterns = patterns_payload.get("patterns", [])
    contexts = contexts_payload.get("contexts", [])

    attribution = _attribute_outcomes_to_contexts(
        decisions, recommendations, hypotheses, patterns
    )

    results = []
    for context in contexts:
        attr = attribution.get(context["id"])
        if attr is None:
            continue
        results.append(_revise_context(context, attr))

    return ContextRevisionReport(
        tenant_id=tenant_id,
        total_contexts=len(contexts),
        contexts_with_outcomes=len(results),
        results=results,
    )


class ContextRevisionStore:
    """Read/compute store: revises a tenant's Contexts on demand.

    Wraps the canonical gateway read stores (Decision/Recommendation/Hypothesis/
    Pattern/Context) and applies the pure revision transform. It performs NO
    writes and creates NO new entity (Memory persistence remains planned per the
    framework).
    """

    def __init__(
        self,
        decision_store: Any,
        recommendation_store: Any,
        hypothesis_store: Any,
        pattern_store: Any,
        context_store: Any,
    ):
        self._decision_store = decision_store
        self._recommendation_store = recommendation_store
        self._hypothesis_store = hypothesis_store
        self._pattern_store = pattern_store
        self._context_store = context_store

    async def revise_for_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> ContextRevisionReport:
        return await build_context_revision(
            tenant_id,
            decision_reader=self._decision_store,
            recommendation_reader=self._recommendation_store,
            hypothesis_reader=self._hypothesis_store,
            pattern_reader=self._pattern_store,
            context_reader=self._context_store,
        )

    async def verify_connection(self) -> None:
        if hasattr(self._decision_store, "verify_connection"):
            await self._decision_store.verify_connection()
