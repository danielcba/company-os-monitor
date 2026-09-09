"""Cognitive Gate — Minimum orchestration to demonstrate the full chain.

Decision → Expected Outcome → Execution → Observed Outcome → Evaluation → Learning Trigger.

This module provides the thin orchestrator that connects a committed Decision
with its observed outcomes and triggers the learning loop. It reuses all
existing H3 infrastructure without introducing a new parallel path.

P6: This function does NOT execute the Decision. It records the observed outcomes
after execution and triggers the learning loop (P7).

R1: single capability — orchestrate the Cognitive Gate chain.
P1: no fabrication — missing outcomes are never treated as failures.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from libs.learning.learning_execution_store import LearningExecutionStore
from libs.memory.learning_loop import H3LearningLoopStore


@dataclass(slots=True)
class CognitiveGateResult:
    """Result of the Cognitive Gate orchestration.

    Chains: Decision → Expected Outcome → Execution → Observed Outcome →
    Evaluation → Learning Trigger.
    """

    tenant_id: uuid.UUID
    decision_id: uuid.UUID
    outcome_revision_id: uuid.UUID
    execution_id: uuid.UUID | None
    learning_status: str  # "completed", "skipped", "failed"
    consolidation_feedback: float
    brier: float
    ece: float
    persisted_signal_count: int


async def submit_decision_outcomes_and_learn(  # noqa: PLR0913
    *,
    tenant_id: uuid.UUID,
    decision_id: uuid.UUID,
    actual_outcomes: list[dict[str, Any]],
    executed_at: datetime | None = None,
    execution_store: LearningExecutionStore,
    learning_loop_store: H3LearningLoopStore,
) -> CognitiveGateResult:
    """Submit observed outcomes for a committed Decision and trigger the learning loop.

    This is the minimum mechanism to demonstrate the Cognitive Gate end-to-end:
    Decision → Expected Outcome → Execution → Observed Outcome → Evaluation → Learning Trigger.

    P6: This function does NOT execute the Decision. It records the observed outcomes
    after execution (P7: learning through outcome).

    Phase 1 (lock-free): INSERT outcome_revision + UPDATE decisions
    Phase 2 (advisory-locked): Learning execution + signal persistence

    Idempotent: re-submitting the same outcomes for the same decision creates a new
    outcome revision (append-only history) but the learning execution is idempotent
    via the UNIQUE partial index.
    """
    # Phase 1: Atomic INSERT outcome_revision + UPDATE decisions (F-02)
    outcome_revision = await execution_store.submit_outcomes_with_revision(
        tenant_id=tenant_id,
        decision_id=decision_id,
        actual_outcomes=actual_outcomes,
        executed_at=executed_at,
    )

    # Phase 2: H3 learning loop (advisory-locked, single transaction — F-01)
    h3_result = await learning_loop_store.run_for_decision(
        tenant_id=tenant_id,
        decision_id=decision_id,
        outcome_revision_id=outcome_revision.id,
    )

    return CognitiveGateResult(
        tenant_id=tenant_id,
        decision_id=decision_id,
        outcome_revision_id=outcome_revision.id,
        execution_id=h3_result.execution_id,
        learning_status=h3_result.status,
        consolidation_feedback=h3_result.consolidation.calibration_feedback,
        brier=h3_result.consolidation.brier,
        ece=h3_result.consolidation.ece,
        persisted_signal_count=len(h3_result.persisted),
    )
