"""Learning Loop (P7) — Automatic feedback: Decision outcomes → Consolidation →
Memory persistence → Pattern/Context/Insight refinement.

The framework (P7): "Learning is not a phase. It is a continuous loop."
This module closes the loop by orchestrating the P7 capabilities automatically
when Decision outcomes are recorded.

It is an external capability (ADR-0002): it consumes canonical read stores and
writes to the Learning Memory ledger (append-only, P1). It never mutates
canonical entities.

R1: single capability — run the full learning loop for a tenant/decision.
P1: no fabrication — missing outcomes are never treated as failures.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from libs.memory.consolidation import ConsolidationResult, build_consolidation
from libs.memory.context_revision import (
    ContextRevisionReport,
    build_context_revision,
)
from libs.memory.insight_transformation import (
    InsightTransformationReport,
    build_insight_transformation,
)
from libs.memory.memory_ledger import (
    LearningMemoryRecord,
    MemoryStoreProtocol,
    PersistLearningMemoryInput,
)
from libs.memory.pattern_refinement import (
    PatternRefinementReport,
    build_pattern_refinement,
)


@runtime_checkable
class DecisionReader(Protocol):
    async def list_decisions(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...

    async def get_decision(
        self, *, tenant_id: uuid.UUID, decision_id: uuid.UUID
    ) -> dict[str, Any] | None:
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
class ContextReader(Protocol):
    async def list_contexts(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class InsightReader(Protocol):
    async def list_insights(
        self, *, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class LearningLoopResult:
    """Result of running the learning loop for one Decision."""

    tenant_id: uuid.UUID
    decision_id: uuid.UUID
    consolidation: ConsolidationResult
    pattern_refinement: PatternRefinementReport
    context_revision: ContextRevisionReport
    insight_transformation: InsightTransformationReport
    persisted: list[LearningMemoryRecord]


class LearningLoopStoreProtocol(Protocol):
    """Contract for the Learning Loop store (testable seam)."""

    async def run_for_decision(
        self, *, tenant_id: uuid.UUID, decision_id: uuid.UUID
    ) -> LearningLoopResult:
        """Execute the full learning loop for a Decision with actual outcomes."""


async def _persist_learning_signal(  # noqa: PLR0913, PLR0917
    *,
    memory_store: MemoryStoreProtocol,
    tenant_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    signal: dict[str, Any],
    provenance: dict[str, Any],
) -> LearningMemoryRecord:
    """Persist one learning signal to the memory ledger (idempotent)."""
    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type=target_type,
        target_id=target_id,
        signal=signal,
        provenance=provenance,
    )
    return await memory_store.persist(record=record)


async def run_learning_loop_for_decision(  # noqa: PLR0913
    tenant_id: uuid.UUID,
    decision_id: uuid.UUID,
    *,
    decision_reader: DecisionReader,
    recommendation_reader: RecommendationReader,
    hypothesis_reader: HypothesisReader,
    pattern_reader: PatternReader,
    context_reader: ContextReader,
    insight_reader: InsightReader,
    memory_store: MemoryStoreProtocol,
) -> LearningLoopResult:
    """Execute the full P7 learning loop for a Decision that has actual outcomes.

    Steps:
    1. Load the Decision and run Consolidation (expected vs actual outcomes).
    2. Run Pattern Refinement for the tenant (attributes outcomes to Patterns).
    3. Run Context Revision for the tenant (attributes outcomes to Contexts).
    4. Run Insight Transformation for the tenant (journals Insight prior→updated).
    5. Persist all signals to the Learning Memory ledger (append-only, idempotent).

    Returns a LearningLoopResult with all computed signals and the persisted records.
    """
    # 1. Load the Decision and run Consolidation
    decision = await decision_reader.get_decision(tenant_id=tenant_id, decision_id=decision_id)
    if decision is None:
        raise ValueError

    # Build a Decision view for consolidation (needs expected/actual outcomes)
    class _DecisionView:
        def __init__(self, d: dict[str, Any]):
            self.id = d.get("id")
            self.tenant_id = d.get("tenant_id")
            self.expected_outcomes = d.get("expected_outcomes") or []
            self.actual_outcomes = d.get("actual_outcomes")

    consolidation = build_consolidation(_DecisionView(decision))

    # 2. Run Pattern Refinement (read/compute over all tenant patterns)
    pattern_refinement = await build_pattern_refinement(
        tenant_id,
        decision_reader=decision_reader,
        recommendation_reader=recommendation_reader,
        hypothesis_reader=hypothesis_reader,
        pattern_reader=pattern_reader,
    )

    # 3. Run Context Revision (read/compute over all tenant contexts)
    context_revision = await build_context_revision(
        tenant_id,
        decision_reader=decision_reader,
        recommendation_reader=recommendation_reader,
        hypothesis_reader=hypothesis_reader,
        pattern_reader=pattern_reader,
        context_reader=context_reader,
    )

    # 4. Run Insight Transformation (read/compute over all tenant insights)
    insight_transformation = await build_insight_transformation(
        tenant_id,
        insight_reader=insight_reader,
        decision_reader=decision_reader,
        recommendation_reader=recommendation_reader,
    )

    # 5. Persist all signals to the Learning Memory ledger
    persisted: list = []

    # Persist the consolidation signal for this decision
    consolidation_signal = {
        "decision_id": str(decision_id),
        "calibration_feedback": consolidation.calibration_feedback,
        "brier": consolidation.brier,
        "ece": consolidation.ece,
        "corroborated": consolidation.corroborated,
        "contradicted": consolidation.contradicted,
        "inconclusive": consolidation.inconclusive,
        "details": consolidation.details,
    }
    consolidation_provenance = {
        "decision_id": str(decision_id),
        "tenant_id": str(tenant_id),
        "source": "outcome_consolidation",
    }
    persisted.append(
        await _persist_learning_signal(
            memory_store,
            tenant_id,
            "pattern",  # consolidation feedback relates to patterns via decisions
            decision_id,
            consolidation_signal,
            consolidation_provenance,
        )
    )

    # Persist Pattern Refinement signals
    for pr in pattern_refinement.results:
        signal = {
            "pattern_id": str(pr.pattern_id),
            "recommended_action": pr.recommended_action,
            "recommended_strength": pr.recommended_strength,
            "current_strength": pr.current_strength,
            "linked_decisions": pr.linked_decisions,
            "corroborated": pr.corroborated,
            "contradicted": pr.contradicted,
            "inconclusive": pr.inconclusive,
            "contradiction_ratio": pr.contradiction_ratio,
        }
        provenance = {
            "pattern_id": str(pr.pattern_id),
            "context_id": str(pr.context_id),
            "tenant_id": str(tenant_id),
            "source": "pattern_refinement",
        }
        persisted.append(
            await _persist_learning_signal(
                memory_store,
                tenant_id,
                "pattern",
                pr.pattern_id,
                signal,
                provenance,
            )
        )

    # Persist Context Revision signals
    for cr in context_revision.results:
        signal = {
            "context_id": str(cr.context_id),
            "recommended_revision": cr.recommended_revision,
            "suggested_competitor": cr.suggested_competitor,
            "linked_decisions": cr.linked_decisions,
            "corroborated": cr.corroborated,
            "contradicted": cr.contradicted,
            "inconclusive": cr.inconclusive,
            "contradiction_ratio": cr.contradiction_ratio,
            "has_competing_models": cr.has_competing_models,
        }
        provenance = {
            "context_id": str(cr.context_id),
            "tenant_id": str(tenant_id),
            "source": "context_revision",
        }
        persisted.append(
            await _persist_learning_signal(
                memory_store,
                tenant_id,
                "context",
                cr.context_id,
                signal,
                provenance,
            )
        )

    # Persist Insight Transformation signals
    for it in insight_transformation.results:
        signal = {
            "insight_id": str(it.insight_id),
            "transformation_kind": it.transformation_kind,
            "description": it.description,
            "prior_understanding": it.prior_understanding,
            "mental_model_update": it.mental_model_update,
            "linked_recommendations": it.linked_recommendations,
            "linked_decisions_with_outcomes": it.linked_decisions_with_outcomes,
            "corroborated": it.corroborated,
            "contradicted": it.contradicted,
            "inconclusive": it.inconclusive,
        }
        provenance = {
            "insight_id": str(it.insight_id),
            "tenant_id": str(tenant_id),
            "source": "insight_transformation",
        }
        persisted.append(
            await _persist_learning_signal(
                memory_store,
                tenant_id,
                "insight",
                it.insight_id,
                signal,
                provenance,
            )
        )

    return LearningLoopResult(
        tenant_id=tenant_id,
        decision_id=decision_id,
        consolidation=consolidation,
        pattern_refinement=pattern_refinement,
        context_revision=context_revision,
        insight_transformation=insight_transformation,
        persisted=persisted,
    )


class LearningLoopStore:
    """Store that runs the full Learning Loop (read/compute + write to ledger).

    Wraps all P7 read/compute capabilities and the Memory Ledger. It performs
    reads from canonical stores and writes to the append-only learning_memory
    ledger. It NEVER mutates canonical entities (P1).
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        decision_store: DecisionReader,
        recommendation_store: RecommendationReader,
        hypothesis_store: HypothesisReader,
        pattern_store: PatternReader,
        context_store: ContextReader,
        insight_store: InsightReader,
        memory_store: MemoryStoreProtocol,
    ):
        self._decision_store = decision_store
        self._recommendation_store = recommendation_store
        self._hypothesis_store = hypothesis_store
        self._pattern_store = pattern_store
        self._context_store = context_store
        self._insight_store = insight_store
        self._memory_store = memory_store

    async def run_for_decision(
        self, *, tenant_id: uuid.UUID, decision_id: uuid.UUID
    ) -> LearningLoopResult:
        return await run_learning_loop_for_decision(
            tenant_id,
            decision_id,
            decision_reader=self._decision_store,
            recommendation_reader=self._recommendation_store,
            hypothesis_reader=self._hypothesis_store,
            pattern_reader=self._pattern_store,
            context_reader=self._context_store,
            insight_reader=self._insight_store,
            memory_store=self._memory_store,
        )

    async def verify_connection(self) -> None:
        for store in (
            self._decision_store,
            self._recommendation_store,
            self._hypothesis_store,
            self._pattern_store,
            self._context_store,
            self._insight_store,
            self._memory_store,
        ):
            if hasattr(store, "verify_connection"):
                await store.verify_connection()

    async def close(self) -> None:
        for store in (
            self._decision_store,
            self._recommendation_store,
            self._hypothesis_store,
            self._pattern_store,
            self._context_store,
            self._insight_store,
            self._memory_store,
        ):
            if hasattr(store, "close"):
                await store.close()