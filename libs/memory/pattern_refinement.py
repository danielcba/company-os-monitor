"""Pattern Refinement (P7 + P4) — Learning Loop extension (read/compute).

The framework (P7): "Learning refines Patterns." When Decisions based on a
Pattern are contradicted by reality, the Pattern's support should be
reconsidered. The framework (P4): Patterns are detected, not invented;
refinement only adjusts support, never fabricates new patterns.

This module is a READ/COMPUTE capability (ADR-0002): it attributes Decision
outcomes to the Patterns that informed them (via the traceability chain
``Decision -> Recommendation -> Hypothesis -> Pattern``) and computes a
refinement signal (keep / degrade / deactivate) for each Pattern. It does NOT
mutate canonical entities — the signal is surfaced for review/action.

Placement: this capability lives under ``libs.memory`` (alongside Outcome
Consolidation), NOT under the reasoning package. The gateway's boundary forbids
importing the reasoning/perception pipeline packages; the external capability
reads canonical data only through the gateway's read stores (dict payloads),
exactly like the consolidation capability.

R1: single capability — compute Pattern refinement from outcomes.
P1: no fabrication — missing/inconclusive outcomes are never counted as failures.
P4: refinement only adjusts support; it never invents or removes patterns.
ADR-0002: external read/compute capability; no new persisted entity.
"""
from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from libs.memory.consolidation import build_consolidation

# Minimum number of linked Decisions with outcomes before a Pattern can be
# recommended for degradation/deactivation (avoids over-reacting to noise).
MIN_SAMPLES_FOR_REFINEMENT = 2
# Contradiction ratio above which a Pattern is recommended for deactivation.
DEACTIVATE_THRESHOLD = 0.5


class _DecisionView:
    """Minimal attribute-view adapter for ``build_consolidation``.

    The gateway read stores return dict payloads; ``build_consolidation`` needs
    attribute access to ``expected_outcomes``/``actual_outcomes``. This adapter
    provides exactly that without pulling ``libs.action`` models into the core.
    """

    def __init__(self, decision: dict[str, Any]):
        self.id = decision.get("id")
        self.tenant_id = decision.get("tenant_id")
        self.expected_outcomes = decision.get("expected_outcomes") or []
        self.actual_outcomes = decision.get("actual_outcomes")


class PatternRefinementResult(BaseModel):
    """Per-Pattern refinement signal (read/compute; never persisted)."""

    pattern_id: uuid.UUID
    pattern_type: str
    context_id: uuid.UUID
    tenant_id: uuid.UUID
    linked_decisions: int
    corroborated: int
    contradicted: int
    inconclusive: int
    contradiction_ratio: float
    current_strength: float
    recommended_strength: float
    recommended_action: str  # "keep" | "degrade" | "deactivate"

    model_config = ConfigDict(frozen=True)


class PatternRefinementReport(BaseModel):
    """Tenant-scoped aggregate of Pattern refinement signals (read/compute)."""

    tenant_id: uuid.UUID
    total_patterns: int
    patterns_with_outcomes: int
    results: list[PatternRefinementResult] = []

    model_config = ConfigDict(frozen=True)


@runtime_checkable
class DecisionReader(Protocol):
    async def list_decisions(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class RecommendationReader(Protocol):
    async def list_recommendations(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class HypothesisReader(Protocol):
    async def list_hypotheses(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class PatternReader(Protocol):
    async def list_patterns(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class PatternRefinementStoreProtocol(Protocol):
    """Structural type for the Pattern Refinement read model (read contract)."""

    async def refine_for_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> PatternRefinementReport:
        """Build the Pattern Refinement signal for ``tenant_id``."""
        ...


def _attribute_outcomes(
    decisions: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Attribute Decision outcome counts to Patterns via the traceability chain.

    Returns ``{pattern_id_str: {corroborated, contradicted, inconclusive, linked}}``.
    The chain is ``Decision.recommendation_id -> Recommendation.hypothesis_id ->
    Hypothesis.pattern_ids -> Pattern``. Missing links are skipped (defensive).
    All identifiers are matched as strings (the gateway read payload shape).
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
            if pattern_id_str not in pat_by_id:
                continue
            attr = attribution.setdefault(
                pattern_id_str,
                {"corroborated": 0, "contradicted": 0, "inconclusive": 0, "linked": 0},
            )
            attr["corroborated"] += corr
            attr["contradicted"] += contr
            attr["inconclusive"] += incon
            attr["linked"] += 1

    return attribution


def _refine_pattern(
    pattern: dict[str, Any], attr: dict[str, int]
) -> PatternRefinementResult:
    """Compute the refinement signal for one Pattern (pure, no IO)."""
    corroborated = attr["corroborated"]
    contradicted = attr["contradicted"]
    inconclusive = attr["inconclusive"]
    linked = attr["linked"]
    total = corroborated + contradicted  # inconclusive does not drive the ratio

    contradiction_ratio = (contradicted / total) if total > 0 else 0.0

    current_strength = float(pattern["strength_measure"])
    if total < MIN_SAMPLES_FOR_REFINEMENT:
        action = "keep"
        recommended_strength = current_strength
    elif contradiction_ratio >= DEACTIVATE_THRESHOLD:
        action = "deactivate"
        recommended_strength = 0.0
    elif contradicted > 0:
        action = "degrade"
        # Degrade proportionally to the corroborated fraction.
        recommended_strength = round(current_strength * (corroborated / total), 4)
    else:
        action = "keep"
        recommended_strength = current_strength

    return PatternRefinementResult(
        pattern_id=uuid.UUID(pattern["id"]),
        pattern_type=pattern["pattern_type"],
        context_id=uuid.UUID(pattern["context_id"]),
        tenant_id=uuid.UUID(pattern["tenant_id"]),
        linked_decisions=linked,
        corroborated=corroborated,
        contradicted=contradicted,
        inconclusive=inconclusive,
        contradiction_ratio=round(contradiction_ratio, 4),
        current_strength=current_strength,
        recommended_strength=recommended_strength,
        recommended_action=action,
    )


async def build_pattern_refinement(
    tenant_id: uuid.UUID,
    *,
    decision_reader: DecisionReader,
    recommendation_reader: RecommendationReader,
    hypothesis_reader: HypothesisReader,
    pattern_reader: PatternReader,
) -> PatternRefinementReport:
    """Build the tenant-scoped Pattern Refinement report (read/compute, no IO).

    Each reader is the gateway's read store, whose ``list_*`` returns a
    paginated dict payload (``{"decisions": [...]}``, ``{"recommendations": [...]}``,
    ``{"hypotheses": [...]}``, ``{"patterns": [...]}``). The capability never
    imports the reasoning/perception pipeline packages (ADR-0002 boundary); it
    only consumes the canonical read contract.
    """
    decisions_payload = await decision_reader.list_decisions(tenant_id=tenant_id)
    recommendations_payload = await recommendation_reader.list_recommendations(
        tenant_id=tenant_id
    )
    hypotheses_payload = await hypothesis_reader.list_hypotheses(tenant_id=tenant_id)
    patterns_payload = await pattern_reader.list_patterns(tenant_id=tenant_id)

    decisions = decisions_payload.get("decisions", [])
    recommendations = recommendations_payload.get("recommendations", [])
    hypotheses = hypotheses_payload.get("hypotheses", [])
    patterns = patterns_payload.get("patterns", [])

    attribution = _attribute_outcomes(
        decisions, recommendations, hypotheses, patterns
    )

    results = []
    for pattern in patterns:
        attr = attribution.get(pattern["id"])
        if attr is None:
            continue
        results.append(_refine_pattern(pattern, attr))

    return PatternRefinementReport(
        tenant_id=tenant_id,
        total_patterns=len(patterns),
        patterns_with_outcomes=len(results),
        results=results,
    )


class PatternRefinementStore:
    """Read/compute store: refines a tenant's Patterns on demand.

    Wraps the canonical gateway read stores (Decision/Recommendation/Hypothesis/
    Pattern) and applies the pure refinement transform. It performs NO writes
    and creates NO new entity (Memory persistence remains planned per the
    framework).
    """

    def __init__(
        self,
        decision_store: DecisionReader,
        recommendation_store: RecommendationReader,
        hypothesis_store: HypothesisReader,
        pattern_store: PatternReader,
    ):
        self._decision_store = decision_store
        self._recommendation_store = recommendation_store
        self._hypothesis_store = hypothesis_store
        self._pattern_store = pattern_store

    async def refine_for_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> PatternRefinementReport:
        return await build_pattern_refinement(
            tenant_id,
            decision_reader=self._decision_store,
            recommendation_reader=self._recommendation_store,
            hypothesis_reader=self._hypothesis_store,
            pattern_reader=self._pattern_store,
        )

    async def verify_connection(self) -> None:
        if hasattr(self._decision_store, "verify_connection"):
            await self._decision_store.verify_connection()
