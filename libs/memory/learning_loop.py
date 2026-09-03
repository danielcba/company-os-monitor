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

H3 (2026-08-31): Durable execution with advisory lock + single transaction.
Phase 2 (learning execution + signal persistence) runs inside a single
advisory-locked transaction per decision, ensuring atomicity and idempotency.
"""
from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


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
class _TraceReaders:
    """Container for traceability readers (avoids PLR0913)."""

    recommendation_reader: RecommendationReader
    hypothesis_reader: HypothesisReader
    pattern_reader: PatternReader
    context_reader: ContextReader
    insight_reader: InsightReader


async def _trace_decision_to_artifacts_bundle(
    decision: dict[str, Any],
    readers: _TraceReaders,
) -> tuple[set[uuid.UUID], set[uuid.UUID], set[uuid.UUID]]:
    """Trace from a Decision to its affected Patterns, Contexts, and Insights.

    Returns (pattern_ids, context_ids, insight_ids) that are linked to this
    Decision through the traceability chain:
    Decision -> Recommendation -> Hypothesis -> Pattern -> Context
    Decision -> Recommendation -> Insight

    This enables decision-scoped learning: only persist signals for artifacts
    actually affected by this Decision's outcomes.
    """
    affected_patterns: set[uuid.UUID] = set()
    affected_contexts: set[uuid.UUID] = set()
    affected_insights: set[uuid.UUID] = set()

    # Get the Recommendation for this Decision
    rec_payload = await readers.recommendation_reader.list_recommendations(
        tenant_id=decision["tenant_id"]
    )
    recommendations = rec_payload.get("recommendations", [])
    rec_by_id = {r["id"]: r for r in recommendations}
    rec = rec_by_id.get(decision.get("recommendation_id"))
    if rec is None:
        return affected_patterns, affected_contexts, affected_insights

    # Get the Hypothesis for this Recommendation
    hyp_payload = await readers.hypothesis_reader.list_hypotheses(
        tenant_id=decision["tenant_id"]
    )
    hypotheses = hyp_payload.get("hypotheses", [])
    hyp_by_id = {h["id"]: h for h in hypotheses}
    hyp = hyp_by_id.get(rec.get("hypothesis_id"))
    if hyp is None:
        return affected_patterns, affected_contexts, affected_insights

    # Get Patterns for this Hypothesis
    pat_payload = await readers.pattern_reader.list_patterns(
        tenant_id=decision["tenant_id"]
    )
    patterns = pat_payload.get("patterns", [])
    pat_by_id = {p["id"]: p for p in patterns}
    for pattern_id_str in hyp.get("pattern_ids") or []:
        pattern = pat_by_id.get(pattern_id_str)
        if pattern is None:
            continue
        affected_patterns.add(uuid.UUID(pattern["id"]))
        context_id_str = pattern.get("context_id")
        if context_id_str:
            affected_contexts.add(uuid.UUID(context_id_str))

    # Get Insight for this Recommendation
    insight_id_str = rec.get("insight_id")
    if insight_id_str:
        affected_insights.add(uuid.UUID(insight_id_str))

    return affected_patterns, affected_contexts, affected_insights


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


# ── H3: Durable Execution Protocol ─────────────────────────────────────────

class H3ExecutionStoreProtocol(Protocol):
    """Protocol for the H3 Learning Execution Store (advisory lock + transaction)."""

    async def begin_execution(
        self,
        *,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        outcome_revision_id: uuid.UUID,
    ) -> Any:
        """Acquire advisory lock and create/claim execution. Returns execution or None."""

    async def begin_phase2(
        self,
        *,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        outcome_revision_id: uuid.UUID,
    ) -> Any:
        """Acquire advisory lock, create/claim execution, return (execution, session).
        The session is inside a transaction with the advisory lock held.
        Caller must commit or rollback the session."""

    async def complete_execution(
        self, *, execution_id: uuid.UUID, signal_count: int
    ) -> Any:
        """Mark execution as completed."""

    async def complete_execution_in_session(
        self, *, session: Any, execution_id: uuid.UUID, signal_count: int
    ) -> Any:
        """Mark execution as completed within the caller's transaction."""

    async def fail_execution(
        self, *, execution_id: uuid.UUID, failure_reason: str
    ) -> Any:
        """Mark execution as failed."""

    async def fail_execution_in_session(
        self, *, session: Any, execution_id: uuid.UUID, failure_reason: str
    ) -> Any:
        """Mark execution as failed within the caller's transaction."""

    async def update_heartbeat(self, *, execution_id: uuid.UUID) -> None:
        """Update heartbeat timestamp (separate transaction)."""


@dataclass(slots=True)
class H3LearningLoopResult:
    """Result of running the H3 learning loop with durable execution."""

    tenant_id: uuid.UUID
    decision_id: uuid.UUID
    execution_id: uuid.UUID | None
    outcome_revision_id: uuid.UUID
    consolidation: ConsolidationResult
    pattern_refinement: PatternRefinementReport
    context_revision: ContextRevisionReport
    insight_transformation: InsightTransformationReport
    persisted: list[LearningMemoryRecord]
    status: str  # "completed", "skipped" (already done), "failed"


class H3LearningLoopStoreProtocol(Protocol):
    """Contract for the H3 Learning Loop store (advisory-locked)."""

    async def run_for_decision(
        self, *, tenant_id: uuid.UUID, decision_id: uuid.UUID
    ) -> H3LearningLoopResult:
        """Execute the full H3 learning loop with durable execution."""


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
    2. Run Pattern Refinement for the tenant (read/compute capability).
    3. Run Context Revision for the tenant (read/compute capability).
    4. Run Insight Transformation for the tenant (read/compute capability).
    5. Trace from Decision to affected Patterns, Contexts, Insights.
    6. Persist signals ONLY for affected artifacts (decision-scoped learning).

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

    # 5. Trace from Decision to affected artifacts
    readers = _TraceReaders(
        recommendation_reader=recommendation_reader,
        hypothesis_reader=hypothesis_reader,
        pattern_reader=pattern_reader,
        context_reader=context_reader,
        insight_reader=insight_reader,
    )
    affected_patterns, affected_contexts, affected_insights = (
        await _trace_decision_to_artifacts_bundle(decision, readers=readers)
    )

    # 6. Persist signals to the Learning Memory ledger (decision-scoped)
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
            "decision",  # consolidation is per-Decision (expected vs actual outcomes)
            decision_id,
            consolidation_signal,
            consolidation_provenance,
        )
    )

    # Persist Pattern Refinement signals (only for affected patterns)
    for pr in pattern_refinement.results:
        if pr.pattern_id not in affected_patterns:
            continue
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
            "decision_id": str(decision_id),  # Full traceability: Decision -> Outcome -> Pattern
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

    # Persist Context Revision signals (only for affected contexts)
    for cr in context_revision.results:
        if cr.context_id not in affected_contexts:
            continue
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
            "decision_id": str(decision_id),  # Full traceability: Decision -> Outcome -> Context
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

    # Persist Insight Transformation signals (only for affected insights)
    for it in insight_transformation.results:
        if it.insight_id not in affected_insights:
            continue
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
            "decision_id": str(decision_id),  # Full traceability: Decision -> Outcome -> Insight
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


# ── H3: Durable Execution Learning Loop ────────────────────────────────────


def _compute_learning_signals(  # noqa: PLR0913
    *,
    decision: dict[str, Any],
    tenant_id: uuid.UUID,
    decision_id: uuid.UUID,
    consolidation: ConsolidationResult,
    pattern_refinement: PatternRefinementReport,
    context_revision: ContextRevisionReport,
    insight_transformation: InsightTransformationReport,
    affected_patterns: set[uuid.UUID],
    affected_contexts: set[uuid.UUID],
    affected_insights: set[uuid.UUID],
) -> list[tuple[str, uuid.UUID, dict[str, Any], dict[str, Any]]]:
    """Compute all learning signals without database access (pure computation).

    Returns list of (target_type, target_id, signal, provenance) tuples.
    These are persisted inside the advisory-locked transaction in Phase 2.
    """
    signals: list[tuple[str, uuid.UUID, dict[str, Any], dict[str, Any]]] = []

    # Consolidation signal for this decision
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
    signals.append(("decision", decision_id, consolidation_signal, consolidation_provenance))

    # Pattern Refinement signals (only affected patterns)
    for pr in pattern_refinement.results:
        if pr.pattern_id not in affected_patterns:
            continue
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
            "decision_id": str(decision_id),
        }
        signals.append(("pattern", pr.pattern_id, signal, provenance))

    # Context Revision signals (only affected contexts)
    for cr in context_revision.results:
        if cr.context_id not in affected_contexts:
            continue
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
            "decision_id": str(decision_id),
        }
        signals.append(("context", cr.context_id, signal, provenance))

    # Insight Transformation signals (only affected insights)
    for it in insight_transformation.results:
        if it.insight_id not in affected_insights:
            continue
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
            "decision_id": str(decision_id),
        }
        signals.append(("insight", it.insight_id, signal, provenance))

    return signals


async def run_h3_learning_loop_for_decision(  # noqa: PLR0913
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
    execution_store: H3ExecutionStoreProtocol,
    outcome_revision_id: uuid.UUID,
) -> H3LearningLoopResult:
    """Execute the H3 learning loop with durable execution (F-01 single transaction).

    Phase 1 (lock-free, already done by caller):
      - outcome_revision already created by the caller
      - Decision.actual_outcomes already updated

    Phase 2 (advisory-locked, single transaction):
      1. Begin execution (acquire lock, create/claim execution) — session stays open
      2. Compute signals (in memory — no DB access)
      3. Persist all signals (same session/transaction)
      4. Complete execution (same session/transaction)
      5. COMMIT — lock auto-released
    """
    # Step 1: Begin execution (advisory lock + state machine) — session stays open
    execution, session = await execution_store.begin_phase2(
        tenant_id=tenant_id,
        decision_id=decision_id,
        outcome_revision_id=outcome_revision_id,
    )

    if execution is None:
        # Already completed or skipped — idempotent. Rollback the unused session.
        await session.rollback()
        return H3LearningLoopResult(
            tenant_id=tenant_id,
            decision_id=decision_id,
            execution_id=None,
            outcome_revision_id=outcome_revision_id,
            consolidation=ConsolidationResult(
                decision_id=decision_id,
                tenant_id=tenant_id,
                has_actuals=False,
                expected_count=0,
                actual_count=0,
                corroborated=0,
                contradicted=0,
                inconclusive=0,
                calibration_feedback=0.0,
                brier=0.0,
                ece=0.0,
                details=[],
            ),
            pattern_refinement=PatternRefinementReport(
                tenant_id=tenant_id,
                total_patterns=0,
                patterns_with_outcomes=0,
                results=[],
            ),
            context_revision=ContextRevisionReport(
                tenant_id=tenant_id,
                total_contexts=0,
                contexts_with_outcomes=0,
                results=[],
            ),
            insight_transformation=InsightTransformationReport(
                tenant_id=tenant_id,
                total_insights=0,
                results=[],
            ),
            persisted=[],
            status="skipped",
        )

    try:
        # Step 2: Compute signals (pure computation, no DB)
        decision = await decision_reader.get_decision(
            tenant_id=tenant_id, decision_id=decision_id
        )
        if decision is None:
            raise ValueError(f"Decision {decision_id} not found")  # noqa: TRY003, TRY301

        class _DecisionView:
            def __init__(self, d: dict[str, Any]):
                self.id = d.get("id")
                self.tenant_id = d.get("tenant_id")
                self.expected_outcomes = d.get("expected_outcomes") or []
                self.actual_outcomes = d.get("actual_outcomes")

        consolidation = build_consolidation(_DecisionView(decision))

        pattern_refinement = await build_pattern_refinement(
            tenant_id,
            decision_reader=decision_reader,
            recommendation_reader=recommendation_reader,
            hypothesis_reader=hypothesis_reader,
            pattern_reader=pattern_reader,
        )

        context_revision = await build_context_revision(
            tenant_id,
            decision_reader=decision_reader,
            recommendation_reader=recommendation_reader,
            hypothesis_reader=hypothesis_reader,
            pattern_reader=pattern_reader,
            context_reader=context_reader,
        )

        insight_transformation = await build_insight_transformation(
            tenant_id,
            insight_reader=insight_reader,
            decision_reader=decision_reader,
            recommendation_reader=recommendation_reader,
        )

        readers = _TraceReaders(
            recommendation_reader=recommendation_reader,
            hypothesis_reader=hypothesis_reader,
            pattern_reader=pattern_reader,
            context_reader=context_reader,
            insight_reader=insight_reader,
        )
        affected_patterns, affected_contexts, affected_insights = (
            await _trace_decision_to_artifacts_bundle(decision, readers=readers)
        )

        # Step 3: Compute all signals (pure computation)
        signal_tuples = _compute_learning_signals(
            decision=decision,
            tenant_id=tenant_id,
            decision_id=decision_id,
            consolidation=consolidation,
            pattern_refinement=pattern_refinement,
            context_revision=context_revision,
            insight_transformation=insight_transformation,
            affected_patterns=affected_patterns,
            affected_contexts=affected_contexts,
            affected_insights=affected_insights,
        )

        # Step 4: Persist all signals (in the advisory-locked transaction)
        persisted: list[LearningMemoryRecord] = []
        for target_type, target_id, signal, provenance in signal_tuples:
            record = PersistLearningMemoryInput(
                tenant_id=tenant_id,
                target_type=target_type,
                target_id=target_id,
                signal=signal,
                provenance=provenance,
                execution_id=execution.id,
            )
            result = await memory_store.persist_in_session(
                session=session, record=record, execution_id=execution.id
            )
            persisted.append(result)

        # Step 5: Complete execution (same transaction)
        await execution_store.complete_execution_in_session(
            session=session,
            execution_id=execution.id,
            signal_count=len(persisted),
        )

        # Step 6: COMMIT — advisory lock auto-released
        await session.commit()

        return H3LearningLoopResult(
            tenant_id=tenant_id,
            decision_id=decision_id,
            execution_id=execution.id,
            outcome_revision_id=outcome_revision_id,
            consolidation=consolidation,
            pattern_refinement=pattern_refinement,
            context_revision=context_revision,
            insight_transformation=insight_transformation,
            persisted=persisted,
            status="completed",
        )

    except Exception as e:
        # Rollback entire Phase 2 transaction — no partial state persisted
        logger.exception(
            "H3 learning loop failed for execution %s — rolling back", execution.id
        )
        await session.rollback()
        # Mark execution as failed in a separate transaction (post-rollback)
        await execution_store.fail_execution(
            execution_id=execution.id,
            failure_reason=str(e),
        )
        raise


class H3LearningLoopStore:
    """H3 Learning Loop store with advisory lock and durable execution.

    Wraps all P7 read/compute capabilities, the Memory Ledger, and the
    Learning Execution Store. Phase 2 runs inside a single advisory-locked
    transaction per decision.
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
        execution_store: H3ExecutionStoreProtocol,
    ):
        self._decision_store = decision_store
        self._recommendation_store = recommendation_store
        self._hypothesis_store = hypothesis_store
        self._pattern_store = pattern_store
        self._context_store = context_store
        self._insight_store = insight_store
        self._memory_store = memory_store
        self._execution_store = execution_store

    async def run_for_decision(
        self,
        *,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        outcome_revision_id: uuid.UUID,
    ) -> H3LearningLoopResult:
        return await run_h3_learning_loop_for_decision(
            tenant_id,
            decision_id,
            decision_reader=self._decision_store,
            recommendation_reader=self._recommendation_store,
            hypothesis_reader=self._hypothesis_store,
            pattern_reader=self._pattern_store,
            context_reader=self._context_store,
            insight_reader=self._insight_store,
            memory_store=self._memory_store,
            execution_store=self._execution_store,
            outcome_revision_id=outcome_revision_id,
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
        if hasattr(self._execution_store, "verify_connection"):
            await self._execution_store.verify_connection()

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
        if hasattr(self._execution_store, "close"):
            await self._execution_store.close()