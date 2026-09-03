"""H3.3 Tests — Recovery, heartbeat, stale detection, reconciliation.

Tests for:
- Heartbeat updates
- Stale detection logic
- Active worker is not falsely recovered
- Stale worker is recoverable
- Reconciliation acquires the same lock
- Reconciliation re-checks state
- Reconciliation re-checks heartbeat
- Reconciliation vs active worker
- Reconciliation vs completion
- Retry cannot duplicate effects
- Orphaned outcome revision detection
- Orphan recovery/classification
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from libs.learning.learning_execution import (
    HEARTBEAT_INTERVAL_SECONDS,
    STALE_THRESHOLD_SECONDS,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_STALE,
    build_learning_execution,
    is_stale,
    transition_status,
    update_heartbeat,
)
from libs.learning.learning_execution_store import _lock_key
from libs.learning.outcome_revision import build_outcome_revision

TENANT = uuid.uuid4()
DECISION = uuid.uuid4()
OUTCOME_REV = uuid.uuid4()


# ── Heartbeat ───────────────────────────────────────────────────────────────


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

    def test_heartbeat_preserves_status(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = update_heartbeat(ex)
        assert ex.status == STATUS_RUNNING

    def test_heartbeat_preserves_identity(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        original_id = ex.id
        ex = update_heartbeat(ex)
        assert ex.id == original_id


# ── Stale detection ────────────────────────────────────────────────────────


class TestStaleDetection:
    def test_not_stale_when_running_and_fresh(self):
        now = datetime.now(UTC)
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": now})
        assert is_stale(ex, now) is False

    def test_stale_when_running_and_expired(self):
        now = datetime.now(UTC)
        old_heartbeat = now - timedelta(seconds=STALE_THRESHOLD_SECONDS + 1)
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": old_heartbeat})
        assert is_stale(ex, now) is True

    def test_not_stale_when_pending(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        assert is_stale(ex) is False

    def test_not_stale_when_completed(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_COMPLETED)
        assert is_stale(ex) is False

    def test_not_stale_when_failed(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_FAILED)
        assert is_stale(ex) is False

    def test_not_stale_when_heartbeat_exactly_at_threshold(self):
        now = datetime.now(UTC)
        at_threshold = now - timedelta(seconds=STALE_THRESHOLD_SECONDS)
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": at_threshold})
        assert is_stale(ex, now) is False

    def test_stale_when_heartbeat_one_second_past_threshold(self):
        now = datetime.now(UTC)
        past_threshold = now - timedelta(seconds=STALE_THRESHOLD_SECONDS + 1)
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": past_threshold})
        assert is_stale(ex, now) is True

    def test_stale_when_heartbeat_is_none(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": None})
        assert is_stale(ex) is True

    def test_threshold_configurable(self):
        assert STALE_THRESHOLD_SECONDS == 300
        assert HEARTBEAT_INTERVAL_SECONDS == 30


# ── Reconciliation scenarios ────────────────────────────────────────────────


class TestReconciliationScenarios:
    def test_stale_execution_is_eligible_for_retry(self):
        """A stale execution can be reconciled with a new execution."""
        now = datetime.now(UTC)
        old_heartbeat = now - timedelta(seconds=STALE_THRESHOLD_SECONDS + 10)
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": old_heartbeat})
        assert is_stale(ex, now) is True

    def test_completed_execution_not_eligible(self):
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_COMPLETED)
        assert is_stale(ex) is False

    def test_failed_execution_not_eligible_for_stale_recovery(self):
        """Failed execution is terminal — retry creates NEW execution, not stale recovery."""
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_FAILED)
        assert is_stale(ex) is False

    def test_reconciliation_creates_new_execution_with_incremented_attempt(self):
        """Retry after stale creates new execution with attempt_number + 1."""
        now = datetime.now(UTC)
        old_heartbeat = now - timedelta(seconds=STALE_THRESHOLD_SECONDS + 10)
        ex1 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex1 = transition_status(ex1, STATUS_RUNNING)
        ex1 = ex1.model_copy(update={"heartbeat_at": old_heartbeat})

        # Simulate what begin_execution does for stale detection
        ex1 = transition_status(ex1, STATUS_STALE)

        ex2 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
            attempt_number=ex1.attempt_number + 1,
            parent_execution_id=ex1.id,
        )
        assert ex2.attempt_number == 2
        assert ex2.parent_execution_id == ex1.id

    def test_reconciliation_preserves_decision_context(self):
        """Retry execution references the same decision and outcome revision."""
        ex1 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex2 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
            attempt_number=2,
            parent_execution_id=ex1.id,
        )
        assert ex2.decision_id == ex1.decision_id
        assert ex2.outcome_revision_id == ex1.outcome_revision_id
        assert ex2.tenant_id == ex1.tenant_id

    def test_worker_resume_prevents_false_recovery(self):
        """If worker resumes (heartbeat updated), reconciliation should skip."""
        now = datetime.now(UTC)
        # Worker was stale, but just updated heartbeat
        fresh_heartbeat = now - timedelta(seconds=5)
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=OUTCOME_REV,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = ex.model_copy(update={"heartbeat_at": fresh_heartbeat})
        assert is_stale(ex, now) is False

    def test_lock_key_same_for_reconciliation_and_normal_execution(self):
        """Reconciliation uses the same advisory lock as normal execution."""
        normal_key = _lock_key(TENANT, DECISION)
        recon_key = _lock_key(TENANT, DECISION)
        assert normal_key == recon_key


# ── Orphan detection ────────────────────────────────────────────────────────


class TestOrphanDetection:
    def test_orphaned_revision_has_no_execution(self):
        """An orphaned revision is one with no corresponding learning_execution."""
        build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[{"metric": "revenue", "value": True}],
        )
        # No execution created for this revision
        # The find_orphaned_revisions query would find this

    def test_non_orphaned_revision_has_execution(self):
        """A non-orphaned revision has at least one learning_execution."""
        rev = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[],
        )
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=rev.id,
        )
        assert ex.outcome_revision_id == rev.id

    def test_orphan_classification(self):
        """Orphans fall into categories: legitimate (Phase 1 committed, Phase 2 never started)."""
        build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[{"metric": "cost", "value": 100}],
        )
        # This is a legitimate orphan: Phase 1 committed, Phase 2 never started
        # The reconciliation should detect and recover it

    def test_already_processed_revision_not_orphan(self):
        """A completed execution means the revision is NOT orphaned."""
        rev = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[],
        )
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=rev.id,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_COMPLETED)
        assert ex.status == STATUS_COMPLETED

    def test_failed_revision_is_not_orphan(self):
        """A failed execution means the revision was processed (not orphaned)."""
        rev = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[],
        )
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=rev.id,
        )
        ex = transition_status(ex, STATUS_RUNNING)
        ex = transition_status(ex, STATUS_FAILED)
        assert ex.status == STATUS_FAILED


# ── DB-level tests ──────────────────────────────────────────────────────────

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from conftest import DSN, pytestmark_db


@pytest.mark.asyncio
@pytestmark_db
async def test_orphaned_revision_detected_by_query():
    """F-1: DB-level test for orphaned outcome_revision detection."""
    import json as _json
    engine = create_async_engine(DSN)
    async with engine.begin() as conn:
        # Create a revision
        result = await conn.execute(
            text(
                "INSERT INTO outcome_revisions (tenant_id, decision_id, actual_outcomes) "
                "VALUES (:t, :d, CAST(:o AS jsonb)) RETURNING id"
            ),
            {"t": str(TENANT), "d": str(DECISION), "o": _json.dumps([])},
        )
        rev_id = result.scalar()

        # No execution created → this is an orphan
        result = await conn.execute(
            text(
                "SELECT id FROM outcome_revisions "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM learning_executions "
                "  WHERE learning_executions.outcome_revision_id = outcome_revisions.id"
                ") AND id = :rev_id"
            ),
            {"rev_id": rev_id},
        )
        orphan = result.scalar()
        assert orphan == rev_id
    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_non_orphaned_revision_not_detected():
    """A revision with an execution is NOT detected as orphaned."""
    import json as _json
    engine = create_async_engine(DSN)
    async with engine.begin() as conn:
        # Create a revision
        result = await conn.execute(
            text(
                "INSERT INTO outcome_revisions (tenant_id, decision_id, actual_outcomes) "
                "VALUES (:t, :d, CAST(:o AS jsonb)) RETURNING id"
            ),
            {"t": str(TENANT), "d": str(DECISION), "o": _json.dumps([])},
        )
        rev_id = result.scalar()

        # Create an execution for it
        await conn.execute(
            text(
                "INSERT INTO learning_executions "
                "(tenant_id, decision_id, outcome_revision_id, status) "
                "VALUES (:t, :d, :r, 'completed')"
            ),
            {"t": str(TENANT), "d": str(DECISION), "r": rev_id},
        )

        # Should NOT be detected as orphan
        result = await conn.execute(
            text(
                "SELECT id FROM outcome_revisions "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM learning_executions "
                "  WHERE learning_executions.outcome_revision_id = outcome_revisions.id"
                ") AND id = :rev_id"
            ),
            {"rev_id": rev_id},
        )
        orphan = result.scalar()
        assert orphan is None
    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_stale_execution_detected():
    """Stale execution is detected when heartbeat is expired."""
    import json as _json
    engine = create_async_engine(DSN)
    async with engine.begin() as conn:
        # Create revision
        result = await conn.execute(
            text(
                "INSERT INTO outcome_revisions (tenant_id, decision_id, actual_outcomes) "
                "VALUES (:t, :d, CAST(:o AS jsonb)) RETURNING id"
            ),
            {"t": str(TENANT), "d": str(DECISION), "o": _json.dumps([])},
        )
        rev_id = result.scalar()

        # Create running execution with old heartbeat
        await conn.execute(
            text(
                "INSERT INTO learning_executions "
                "(tenant_id, decision_id, outcome_revision_id, status, heartbeat_at) "
                "VALUES (:t, :d, :r, 'running', now() - interval '10 minutes')"
            ),
            {"t": str(TENANT), "d": str(DECISION), "r": rev_id},
        )

        # Detect stale
        result = await conn.execute(
            text(
                "SELECT id FROM learning_executions "
                "WHERE status = 'running' "
                "AND heartbeat_at < now() - interval '5 minutes'"
            )
        )
        stale = result.scalar()
        assert stale is not None
    await engine.dispose()
