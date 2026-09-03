"""H3.0 Tests — Learning Execution state machine, Outcome Revision, schema.

Unit tests for the durable execution lifecycle model (P2: deterministic
state machine) and append-only outcome revision model (P6).
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from libs.learning.learning_execution import (
    HEARTBEAT_INTERVAL_SECONDS,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_STALE,
    TERMINAL_STATUSES,
    VALID_STATUSES,
    VALID_TRANSITIONS,
    build_learning_execution,
    is_stale,
    transition_status,
    update_heartbeat,
)
from libs.learning.outcome_revision import (
    build_outcome_revision,
)

TENANT = uuid.uuid4()
DECISION = uuid.uuid4()
OUTCOME_REV = uuid.uuid4()


# ── Learning Execution: creation ────────────────────────────────────────────


class TestLearningExecutionCreation:
    def test_creates_in_pending_status(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        assert ex.status == STATUS_PENDING
        assert ex.attempt_number == 1
        assert ex.parent_execution_id is None
        assert ex.signal_count == 0
        assert ex.failure_reason is None

    def test_execution_is_frozen(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        with pytest.raises(Exception):
            ex.status = STATUS_RUNNING  # type: ignore[misc]

    def test_execution_has_unique_id(self):
        ex1 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex2 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        assert ex1.id != ex2.id

    def test_execution_records_created_at(self):
        before = datetime.now(UTC)
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        after = datetime.now(UTC)
        assert before <= ex.created_at <= after

    def test_attempt_number_and_parent_preserved(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
            attempt_number=3,
            parent_execution_id=uuid.uuid4(),
        )
        assert ex.attempt_number == 3
        assert ex.parent_execution_id is not None


# ── Learning Execution: state machine ───────────────────────────────────────


class TestStateMachine:
    def test_valid_statuses_are_complete(self):
        assert STATUS_PENDING in VALID_STATUSES
        assert STATUS_RUNNING in VALID_STATUSES
        assert STATUS_COMPLETED in VALID_STATUSES
        assert STATUS_FAILED in VALID_STATUSES
        assert STATUS_STALE in VALID_STATUSES

    def test_terminal_statuses(self):
        assert STATUS_COMPLETED in TERMINAL_STATUSES
        assert STATUS_FAILED in TERMINAL_STATUSES
        assert STATUS_STALE in TERMINAL_STATUSES
        assert STATUS_PENDING not in TERMINAL_STATUSES
        assert STATUS_RUNNING not in TERMINAL_STATUSES

    def test_pending_to_running(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex2 = transition_status(ex, STATUS_RUNNING)
        assert ex2.status == STATUS_RUNNING
        assert ex2.started_at is not None
        assert ex2.heartbeat_at is not None

    def test_running_to_completed(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_COMPLETED)
        assert ex.status == STATUS_COMPLETED
        assert ex.completed_at is not None

    def test_running_to_failed(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_FAILED)
        assert ex.status == STATUS_FAILED
        assert ex.completed_at is not None

    def test_running_to_stale(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_STALE)
        assert ex.status == STATUS_STALE
        assert ex.completed_at is not None

    def test_invalid_transition_pending_to_completed(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        with pytest.raises(ValueError, match="Invalid transition"):
            transition_status(ex, STATUS_COMPLETED)

    def test_invalid_transition_pending_to_failed(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        with pytest.raises(ValueError, match="Invalid transition"):
            transition_status(ex, STATUS_FAILED)

    def test_invalid_transition_completed_to_running(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_COMPLETED)
        with pytest.raises(ValueError, match="Invalid transition"):
            transition_status(ex, STATUS_RUNNING)

    def test_invalid_transition_unknown_status(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        with pytest.raises(ValueError, match="Invalid transition"):
            transition_status(ex, "unknown")

    def test_valid_transitions_map_is_complete(self):
        """Every valid status has an entry in the transition map."""
        for status in VALID_STATUSES:
            assert status in VALID_TRANSITIONS, f"Missing transition for {status}"

    def test_terminal_statuses_have_no_outgoing_transitions(self):
        for status in TERMINAL_STATUSES:
            assert len(VALID_TRANSITIONS[status]) == 0, (
                f"Terminal status {status} has outgoing transitions"
            )


# ── Learning Execution: heartbeat ───────────────────────────────────────────


class TestHeartbeat:
    def test_heartbeat_updates_timestamp(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        old_hb = ex.heartbeat_at
        ex = update_heartbeat(ex)
        assert ex.heartbeat_at >= old_hb

    def test_is_stale_returns_false_when_running_and_fresh(self):
        now = datetime.now(UTC)
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": now})
        assert is_stale(ex, now) is False

    def test_is_stale_returns_true_when_running_and_expired(self):
        now = datetime.now(UTC)
        stale_threshold = HEARTBEAT_INTERVAL_SECONDS * 10 + 1
        old_heartbeat = now - timedelta(seconds=stale_threshold)
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": old_heartbeat})
        assert is_stale(ex, now) is True

    def test_is_stale_returns_false_when_pending(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        assert is_stale(ex) is False

    def test_is_stale_returns_false_when_completed(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_COMPLETED)
        assert is_stale(ex) is False

    def test_is_stale_returns_true_when_heartbeat_none(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": None})
        assert is_stale(ex) is True


# ── Outcome Revision ────────────────────────────────────────────────────────


class TestOutcomeRevision:
    def test_creates_with_required_fields(self):
        rev = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[{"verifiable_by": "revenue", "value": True}],
        )
        assert rev.tenant_id == TENANT
        assert rev.decision_id == DECISION
        assert len(rev.actual_outcomes) == 1
        assert rev.executed_at is None

    def test_revision_is_frozen(self):
        rev = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[],
        )
        with pytest.raises(Exception):
            rev.actual_outcomes = []  # type: ignore[misc]

    def test_revision_has_unique_id(self):
        r1 = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[],
        )
        r2 = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[],
        )
        assert r1.id != r2.id

    def test_revision_records_created_at(self):
        before = datetime.now(UTC)
        rev = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[],
        )
        after = datetime.now(UTC)
        assert before <= rev.created_at <= after

    def test_revision_with_executed_at(self):
        ts = datetime.now(UTC)
        rev = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[],
            executed_at=ts,
        )
        assert rev.executed_at == ts

    def test_multiple_revisions_for_same_decision(self):
        """P6: append-only — multiple revisions create auditable history."""
        revisions = []
        for _ in range(5):
            revisions.append(
                build_outcome_revision(
                    tenant_id=TENANT,
                    decision_id=DECISION,
                    actual_outcomes=[{"iteration": len(revisions)}],
                )
            )
        ids = {r.id for r in revisions}
        assert len(ids) == 5, "Each revision must have a unique ID"
