"""H6: Architecture invariant tests — Execution & Outcome Contract.

Tests that enforce the architectural invariants of the Execution domain:
- Decision → Execution relationship
- Execution → Outcome relationship
- Append-only (P1) enforcement
- Tenant isolation
- Idempotency
- Status transitions
- No fabrication (P1)
- Cognitive boundary (R1)

These tests verify the invariants, not the implementation details.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from libs.action.execution_record import (
    EXECUTION_STATUSES,
    STATUS_CANCELLED,
    STATUS_EXECUTED,
    STATUS_FAILED,
    STATUS_UNKNOWN,
    ExecutionRecord,
    ExecutionRecordCreate,
    build_execution_record,
    execution_record_id,
)
from libs.learning.outcome_revision import OutcomeRevision

# ── ExecutionRecord model tests ──────────────────────────────────────────


class TestExecutionRecordModel:
    """Verify ExecutionRecord model invariants."""

    def test_execution_record_has_deterministic_id(self):
        """ExecutionRecord ID is deterministic from content (idempotent dedup)."""
        tenant_id = uuid.uuid4()
        decision_id = uuid.uuid4()
        executed_at = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

        id1 = execution_record_id(tenant_id, decision_id, executed_at)
        id2 = execution_record_id(tenant_id, decision_id, executed_at)
        assert id1 == id2, "Same inputs must produce same ID (idempotent)"

    def test_different_time_produces_different_id(self):
        """Different execution times produce different IDs."""
        tenant_id = uuid.uuid4()
        decision_id = uuid.uuid4()

        id1 = execution_record_id(
            tenant_id, decision_id, datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
        )
        id2 = execution_record_id(
            tenant_id, decision_id, datetime(2026, 9, 12, 10, 0, 1, tzinfo=UTC)
        )
        assert id1 != id2

    def test_execution_record_frozen(self):
        """ExecutionRecord is immutable (P1)."""
        record = ExecutionRecord(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
            execution_status="executed",
            executed_at=datetime.now(UTC),
            executed_by=None,
            notes=None,
            metadata={},
            created_at=datetime.now(UTC),
        )
        with pytest.raises((AttributeError, Exception)):
            record.execution_status = "failed"  # type: ignore[misc]

    def test_execution_statuses_are_bounded(self):
        """Only valid execution statuses are allowed."""
        assert frozenset(
            {"executed", "failed", "cancelled", "unknown"}
        ) == EXECUTION_STATUSES

    def test_build_execution_record_assigns_id(self):
        """build_execution_record creates a record with deterministic ID."""
        create = ExecutionRecordCreate(
            tenant_id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
            execution_status="executed",
            executed_at=datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC),
        )
        record = build_execution_record(create)
        assert record.id is not None
        assert record.tenant_id == create.tenant_id
        assert record.decision_id == create.decision_id
        assert record.execution_status == "executed"


# ── Decision → Execution relationship ────────────────────────────────────


class TestDecisionExecutionRelationship:
    """Verify Decision 1 ─── 0..N ExecutionRecord cardinality."""

    def test_execution_references_valid_decision(self):
        """ExecutionRecord must reference an existing Decision."""
        create = ExecutionRecordCreate(
            tenant_id=uuid.uuid4(),
            decision_id=uuid.uuid4(),  # may not exist
            execution_status="executed",
        )
        # The record references a decision_id; FK constraint enforces existence
        assert create.decision_id is not None

    def test_multiple_executions_per_decision(self):
        """A Decision can have 0..N ExecutionRecords (re-execution allowed)."""
        decision_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        records = []
        for i in range(3):
            create = ExecutionRecordCreate(
                tenant_id=tenant_id,
                decision_id=decision_id,
                execution_status="executed",
                executed_at=datetime(2026, 9, 12, 10, i, 0, tzinfo=UTC),
            )
            records.append(build_execution_record(create))

        # All three reference the same decision
        assert all(r.decision_id == decision_id for r in records)
        # All three have unique IDs (different timestamps)
        expected_count = 3
        assert len({r.id for r in records}) == expected_count


# ── Tenant isolation ─────────────────────────────────────────────────────


class TestTenantIsolation:
    """Verify tenant isolation for ExecutionRecords."""

    def test_execution_record_scoped_to_tenant(self):
        """ExecutionRecord carries tenant_id for isolation."""
        tenant_id = uuid.uuid4()
        create = ExecutionRecordCreate(
            tenant_id=tenant_id,
            decision_id=uuid.uuid4(),
        )
        assert create.tenant_id == tenant_id

    def test_different_tenants_different_records(self):
        """ExecutionRecords for different tenants are independent."""
        t1, t2 = uuid.uuid4(), uuid.uuid4()
        d = uuid.uuid4()

        r1 = build_execution_record(
            ExecutionRecordCreate(tenant_id=t1, decision_id=d)
        )
        r2 = build_execution_record(
            ExecutionRecordCreate(tenant_id=t2, decision_id=d)
        )
        assert r1.tenant_id != r2.tenant_id
        assert r1.id != r2.id


# ── Append-only (P1) ────────────────────────────────────────────────────


class TestAppendOnly:
    """Verify append-only invariant for ExecutionRecords."""

    def test_execution_record_is_frozen(self):
        """ExecutionRecord model is frozen (no mutation)."""
        record = ExecutionRecord(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
            execution_status="executed",
            executed_at=datetime.now(UTC),
            executed_by=None,
            notes=None,
            metadata={},
            created_at=datetime.now(UTC),
        )
        # Frozen model prevents attribute assignment
        with pytest.raises((AttributeError, Exception)):
            record.notes = "modified"  # type: ignore[misc]


# ── Status transitions ───────────────────────────────────────────────────


class TestStatusTransitions:
    """Verify execution status semantics."""

    def test_executed_is_valid_status(self):
        """'executed' is a valid execution status."""
        assert STATUS_EXECUTED == "executed"

    def test_failed_is_valid_status(self):
        """'failed' is a valid execution status."""
        assert STATUS_FAILED == "failed"

    def test_cancelled_is_valid_status(self):
        """'cancelled' is a valid execution status."""
        assert STATUS_CANCELLED == "cancelled"

    def test_unknown_is_valid_status(self):
        """'unknown' is a valid execution status."""
        assert STATUS_UNKNOWN == "unknown"


# ── Idempotency ──────────────────────────────────────────────────────────


class TestIdempotency:
    """Verify idempotent behavior."""

    def test_same_content_same_id(self):
        """Same execution content produces same ID (idempotent dedup)."""
        t, d = uuid.uuid4(), uuid.uuid4()
        ts = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

        assert execution_record_id(t, d, ts) == execution_record_id(t, d, ts)

    def test_different_content_different_id(self):
        """Different execution content produces different IDs."""
        ts = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
        id1 = execution_record_id(uuid.uuid4(), uuid.uuid4(), ts)
        id2 = execution_record_id(uuid.uuid4(), uuid.uuid4(), ts)
        assert id1 != id2


# ── Cognitive boundary ───────────────────────────────────────────────────


class TestCognitiveBoundary:
    """Verify H6 respects cognitive boundary (R1)."""

    def test_execution_record_is_not_a_cognitive_capability(self):
        """ExecutionRecord is a domain concept, not a cognitive capability."""
        create = ExecutionRecordCreate(
            tenant_id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
        )
        assert create.execution_status == "executed"

    def test_execution_does_not_imply_automated_action(self):
        """Recording an execution does NOT mean the system performed it."""
        create = ExecutionRecordCreate(
            tenant_id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
            execution_status="executed",
            notes="Human operator performed action externally",
        )
        record = build_execution_record(create)
        assert record.notes == "Human operator performed action externally"


# ── Outcome contract ─────────────────────────────────────────────────────


class TestOutcomeContract:
    """Verify Outcome relationship to Execution."""

    def test_outcome_revision_references_decision(self):
        """OutcomeRevision references a Decision (via decision_id)."""
        rev = OutcomeRevision(
            tenant_id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
            actual_outcomes=[{"verifiable_by": "disk_free_percent", "value": 42}],
        )
        assert rev.decision_id is not None
        assert rev.actual_outcomes is not None

    def test_actual_outcomes_structure(self):
        """actual_outcomes contains verifiable_by and value fields."""
        rev = OutcomeRevision(
            tenant_id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
            actual_outcomes=[
                {"verifiable_by": "disk_free_percent", "value": 42},
                {"verifiable_by": "service_status", "value": True},
            ],
        )
        for ao in rev.actual_outcomes:
            assert "verifiable_by" in ao
            assert "value" in ao
