"""Learning Execution model (H3 — durable execution lifecycle).

Tracks the lifecycle of each learning execution through a deterministic state
machine. An execution is created for each outcome_revision and follows:

    pending → running → completed | failed | stale

Advisory lock (transaction-scoped) serializes concurrent executions for the
same decision. The UNIQUE partial index prevents duplicate active executions
per outcome_revision.

P1: execution content is immutable once created (status transitions only).
P2: deterministic lifecycle — every execution follows a valid state machine.
P7: learning execution closes the loop on decision outcomes.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ── Valid statuses ──────────────────────────────────────────────────────────

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_STALE = "stale"

VALID_STATUSES: frozenset[str] = frozenset(
    {STATUS_PENDING, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED, STATUS_STALE}
)

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {STATUS_COMPLETED, STATUS_FAILED, STATUS_STALE}
)

# ── State machine ───────────────────────────────────────────────────────────
# Maps current status → set of valid next statuses.
# Invalid transitions must fail deterministically (P2).

VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_PENDING: frozenset({STATUS_RUNNING}),
    STATUS_RUNNING: frozenset({STATUS_COMPLETED, STATUS_FAILED, STATUS_STALE}),
    STATUS_COMPLETED: frozenset(),  # terminal — no transitions
    STATUS_FAILED: frozenset(),     # terminal — retry creates NEW execution
    STATUS_STALE: frozenset(),      # terminal — retry creates NEW execution
}


def is_valid_transition(current: str, next_status: str) -> bool:
    """Check whether a state transition is valid per the state machine (P2)."""
    if current not in VALID_STATUSES:
        return False
    return next_status in VALID_TRANSITIONS.get(current, frozenset())


# ── Heartbeat defaults ──────────────────────────────────────────────────────

HEARTBEAT_INTERVAL_SECONDS = 30
STALE_THRESHOLD_SECONDS = 300


# ── Model ───────────────────────────────────────────────────────────────────

class LearningExecution(BaseModel):
    """Immutable identity + mutable lifecycle of a learning execution.

    Content fields (tenant_id, decision_id, outcome_revision_id, attempt_number,
    parent_execution_id) are set at creation and never change (P1).
    Status transitions follow the deterministic state machine (P2).
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    decision_id: uuid.UUID
    outcome_revision_id: uuid.UUID
    status: str = STATUS_PENDING
    attempt_number: int = 1
    parent_execution_id: uuid.UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    heartbeat_at: datetime | None = None
    signal_count: int = 0
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


def build_learning_execution(
    *,
    tenant_id: uuid.UUID,
    decision_id: uuid.UUID,
    outcome_revision_id: uuid.UUID,
    attempt_number: int = 1,
    parent_execution_id: uuid.UUID | None = None,
) -> LearningExecution:
    """Create a new learning execution in pending status (P2: deterministic lifecycle)."""
    return LearningExecution(
        tenant_id=tenant_id,
        decision_id=decision_id,
        outcome_revision_id=outcome_revision_id,
        attempt_number=attempt_number,
        parent_execution_id=parent_execution_id,
        status=STATUS_PENDING,
    )


def transition_status(execution: LearningExecution, new_status: str) -> LearningExecution:
    """Transition an execution to a new status.

    Raises ValueError if the transition is invalid (P2: deterministic lifecycle).
    Returns a new LearningExecution with the updated status (frozen model).
    """
    if not is_valid_transition(execution.status, new_status):
        raise ValueError("Invalid transition")  # noqa: TRY003
    now = datetime.now(UTC)
    updates: dict[str, Any] = {"status": new_status}

    if new_status == STATUS_RUNNING:
        updates["started_at"] = now
        updates["heartbeat_at"] = now
    elif new_status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_STALE):
        updates["completed_at"] = now

    return execution.model_copy(update=updates)


def update_heartbeat(execution: LearningExecution) -> LearningExecution:
    """Update the heartbeat timestamp (separate transaction, no status change)."""
    return execution.model_copy(update={"heartbeat_at": datetime.now(UTC)})


def is_stale(execution: LearningExecution, now: datetime | None = None) -> bool:
    """Determine if an execution is stale: status=running AND heartbeat expired."""
    if execution.status != STATUS_RUNNING:
        return False
    if execution.heartbeat_at is None:
        return True
    reference = now or datetime.now(UTC)
    elapsed = (reference - execution.heartbeat_at).total_seconds()
    return elapsed > STALE_THRESHOLD_SECONDS
