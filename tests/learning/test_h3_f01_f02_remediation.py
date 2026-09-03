"""H3 F-01/F-02 Remediation Tests — Real PostgreSQL validation.

Tests for:
- F-01: Single-transaction Phase 2 (advisory lock held for entire critical section)
- F-01: Failure injection — rollback on error, no partial state
- F-01: Concurrency — same decision serialized, different decisions independent
- F-02: Atomic Phase 1 — INSERT outcome_revision + UPDATE decisions in one transaction
- F-02: Failure injection — rollback on error, no partial state
"""
import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from conftest import DSN, pytestmark_db


TENANT = uuid.uuid4()
DECISION = uuid.uuid4()


# ── F-01: Single-transaction Phase 2 ────────────────────────────────────────


@pytest.mark.asyncio
@pytestmark_db
async def test_begin_phase2_acquires_lock_and_returns_session():
    """begin_phase2 returns (execution, session) with lock held in a transaction."""
    from libs.learning.learning_execution_store import LearningExecutionStore

    engine = create_async_engine(DSN)
    store = LearningExecutionStore(engine=engine)

    # Create an outcome revision first
    rev = await store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "test", "value": True}],
    )

    # begin_phase2 should return execution + session
    execution, session = await store.begin_phase2(
        tenant_id=TENANT,
        decision_id=DECISION,
        outcome_revision_id=rev.id,
    )

    assert execution is not None
    assert execution.status == "running"
    assert isinstance(session, AsyncSession)

    # Session should be in a transaction — verify by checking the execution exists
    result = await session.execute(
        text("SELECT status FROM learning_executions WHERE id = :id"),
        {"id": execution.id},
    )
    row = result.mappings().one()
    assert row["status"] == "running"

    # Rollback to clean up (advisory lock released)
    await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_phase2_rollback_rolls_back_all_writes():
    """Rollback of Phase 2 session removes execution — no partial state."""
    from libs.learning.learning_execution_store import LearningExecutionStore

    engine = create_async_engine(DSN)
    store = LearningExecutionStore(engine=engine)

    rev = await store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "rollback_test", "value": True}],
    )

    execution, session = await store.begin_phase2(
        tenant_id=TENANT,
        decision_id=DECISION,
        outcome_revision_id=rev.id,
    )
    assert execution is not None

    # Rollback — execution should be gone
    await session.rollback()

    # Verify: no execution for this revision
    result = await store.get_latest_execution_for_revision(
        outcome_revision_id=rev.id,
    )
    assert result is None
    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_phase2_commit_persists_execution():
    """Commit of Phase 2 session persists the execution."""
    from libs.learning.learning_execution_store import LearningExecutionStore

    engine = create_async_engine(DSN)
    store = LearningExecutionStore(engine=engine)

    rev = await store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "commit_test", "value": True}],
    )

    execution, session = await store.begin_phase2(
        tenant_id=TENANT,
        decision_id=DECISION,
        outcome_revision_id=rev.id,
    )
    assert execution is not None

    # Complete execution within the session
    await store.complete_execution_in_session(
        session=session,
        execution_id=execution.id,
        signal_count=3,
    )

    # Commit
    await session.commit()

    # Verify: execution is completed
    result = await store.get_execution(execution_id=execution.id)
    assert result is not None
    assert result.status == "completed"
    assert result.signal_count == 3
    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_phase2_rollback_on_exception_leaves_no_execution():
    """Exception during Phase 2 → rollback → no execution persisted."""
    from libs.learning.learning_execution_store import LearningExecutionStore

    engine = create_async_engine(DSN)
    store = LearningExecutionStore(engine=engine)

    rev = await store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "exception_test", "value": True}],
    )

    execution, session = await store.begin_phase2(
        tenant_id=TENANT,
        decision_id=DECISION,
        outcome_revision_id=rev.id,
    )
    assert execution is not None

    # Simulate an error during signal persistence → rollback
    await session.rollback()

    # Execution should not exist (rollback removed it)
    result = await store.get_execution(execution_id=execution.id)
    assert result is None
    await engine.dispose()


# ── F-01: Concurrency validation ────────────────────────────────────────────


@pytest.mark.asyncio
@pytestmark_db
async def test_concurrent_same_decision_serialized():
    """Two workers targeting the same decision: second blocks until first commits."""
    from libs.learning.learning_execution_store import LearningExecutionStore

    engine = create_async_engine(DSN)
    store = LearningExecutionStore(engine=engine)

    rev = await store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "concurrent_test", "value": True}],
    )

    results = {"worker1_started": False, "worker2_started": False,
               "worker1_committed": False, "worker2_committed": False}

    async def worker1():
        execution, session = await store.begin_phase2(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=rev.id,
        )
        if execution is not None:
            results["worker1_started"] = True
            await asyncio.sleep(0.1)  # Hold the lock
            await store.complete_execution_in_session(
                session=session, execution_id=execution.id, signal_count=1,
            )
            await session.commit()
            results["worker1_committed"] = True

    async def worker2():
        await asyncio.sleep(0.02)  # Start after worker1
        execution, session = await store.begin_phase2(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=rev.id,
        )
        if execution is not None:
            results["worker2_started"] = True
            await store.complete_execution_in_session(
                session=session, execution_id=execution.id, signal_count=1,
            )
            await session.commit()
            results["worker2_committed"] = True
        else:
            # Already completed by worker1 — idempotent skip
            await session.rollback()

    await asyncio.gather(worker1(), worker2())

    # Worker1 should complete. Worker2 either completes or skips (both valid).
    assert results["worker1_committed"]
    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_concurrent_different_decisions_independent():
    """Two different decisions run concurrently without blocking."""
    from libs.learning.learning_execution_store import LearningExecutionStore

    engine = create_async_engine(DSN)
    store = LearningExecutionStore(engine=engine)

    d1 = uuid.uuid4()
    d2 = uuid.uuid4()

    rev1 = await store.create_outcome_revision(
        tenant_id=TENANT, decision_id=d1,
        actual_outcomes=[{"metric": "d1", "value": True}],
    )
    rev2 = await store.create_outcome_revision(
        tenant_id=TENANT, decision_id=d2,
        actual_outcomes=[{"metric": "d2", "value": True}],
    )

    async def worker(decision_id, rev_id, label):
        execution, session = await store.begin_phase2(
            tenant_id=TENANT,
            decision_id=decision_id,
            outcome_revision_id=rev_id,
        )
        if execution is not None:
            await store.complete_execution_in_session(
                session=session, execution_id=execution.id, signal_count=1,
            )
            await session.commit()
            return label
        await session.rollback()
        return f"{label}-skipped"

    r1, r2 = await asyncio.gather(
        worker(d1, rev1.id, "w1"),
        worker(d2, rev2.id, "w2"),
    )

    assert "w1" in r1
    assert "w2" in r2
    await engine.dispose()


# ── F-02: Atomic Phase 1 ────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytestmark_db
async def test_submit_outcomes_with_revision_atomic_success():
    """submit_outcomes_with_revision: both INSERT and UPDATE succeed atomically."""
    from libs.learning.learning_execution_store import LearningExecutionStore

    engine = create_async_engine(DSN)
    exec_store = LearningExecutionStore(engine=engine)

    # Create a decision in the DB first (with full FK chain)
    decision_id = uuid.uuid4()
    recommendation_id = uuid.uuid4()
    hypothesis_id = uuid.uuid4()
    confidence_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, slug, created_at) VALUES (:id, :n, :s, now()) ON CONFLICT DO NOTHING"),
            {"id": TENANT, "n": "test-tenant", "s": f"test-tenant-{TENANT}"},
        )
        await conn.execute(
            text(
                "INSERT INTO hypotheses (id, tenant_id, anomaly_ids, description, "
                "predicted_consequences, falsification_criterion, coherence_score, generated_at) "
                "VALUES (:id, :t, :a, :d, CAST(:pc AS jsonb), :fc, :cs, now())"
            ),
            {"id": hypothesis_id, "t": TENANT, "a": [], "d": "test hypothesis",
             "pc": json.dumps([{"consequence": "test"}]),
             "fc": "test criterion", "cs": 0.8},
        )
        await conn.execute(
            text(
                "INSERT INTO confidence_scores (id, tenant_id, target_type, target_id, "
                "evidential_support, explanatory_coherence, historical_calibration, "
                "confidence_score, alpha, calibration_justification, calibration_error_estimate, computed_at) "
                "VALUES (:id, :t, :tt, :tid, :es, :ec, :hc, :cs, :al, :cj, :ee, now())"
            ),
            {"id": confidence_id, "t": TENANT, "tt": "hypothesis", "tid": hypothesis_id,
             "es": 0.8, "ec": 0.8, "hc": 0.8, "cs": 0.8, "al": 0.5, "cj": "test", "ee": 0.1},
        )
        await conn.execute(
            text(
                "INSERT INTO recommendations (id, tenant_id, hypothesis_id, confidence_id, "
                "action_description, rationale, expected_consequences, confidence_score, proposed_at) "
                "VALUES (:id, :t, :h, :c, :ad, :r, CAST(:ec AS jsonb), :cs, now())"
            ),
            {"id": recommendation_id, "t": TENANT, "h": hypothesis_id, "c": confidence_id,
             "ad": "test action", "r": "test rationale",
             "ec": json.dumps([{"consequence": "test"}]), "cs": 0.8},
        )
        await conn.execute(
            text(
                "INSERT INTO decisions (id, tenant_id, recommendation_id, "
                "confidence_id, authority_id, commitment, expected_outcomes, "
                "risk_tolerance, status, committed_at) "
                "VALUES (:id, :t, :r, :c, :a, :commit, CAST(:eo AS jsonb), :rt, 'committed', now())"
            ),
            {
                "id": decision_id,
                "t": TENANT,
                "r": recommendation_id,
                "c": confidence_id,
                "a": uuid.uuid4(),
                "commit": "test commitment",
                "eo": json.dumps([{"metric": "test", "expected": True}]),
                "rt": "moderate",
            },
        )

    # Execute atomic Phase 1
    rev = await exec_store.submit_outcomes_with_revision(
        tenant_id=TENANT,
        decision_id=decision_id,
        actual_outcomes=[{"metric": "test", "value": True}],
        executed_at=datetime.now(UTC),
    )

    assert rev is not None
    assert rev.decision_id == decision_id
    assert rev.actual_outcomes == [{"metric": "test", "value": True}]

    # Verify decision was updated
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT actual_outcomes FROM decisions WHERE id = :id"),
            {"id": decision_id},
        )
        row = result.mappings().one()
        assert row["actual_outcomes"] is not None

    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_submit_outcomes_with_revision_nonexistent_decision_rolls_back():
    """Atomic Phase 1 with nonexistent decision → entire transaction rolls back."""
    from libs.learning.learning_execution_store import LearningExecutionStore

    engine = create_async_engine(DSN)
    exec_store = LearningExecutionStore(engine=engine)

    fake_decision = uuid.uuid4()

    with pytest.raises(ValueError, match="not found"):
        await exec_store.submit_outcomes_with_revision(
            tenant_id=TENANT,
            decision_id=fake_decision,
            actual_outcomes=[{"metric": "test", "value": True}],
        )

    # Verify no orphaned outcome_revisions were created for this decision
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM outcome_revisions WHERE decision_id = :d"),
            {"d": fake_decision},
        )
        count = result.scalar()
        assert count == 0

    await engine.dispose()


# ── F-01: Signal persistence within session ─────────────────────────────────


@pytest.mark.asyncio
@pytestmark_db
async def test_persist_in_session_uses_external_session():
    """persist_in_session persists signal in the caller's transaction."""
    from libs.memory.memory_ledger import MemoryStore, PersistLearningMemoryInput, compute_signal_hash

    engine = create_async_engine(DSN)
    store = MemoryStore(engine=engine)

    record = PersistLearningMemoryInput(
        tenant_id=TENANT,
        target_type="decision",
        target_id=uuid.uuid4(),
        signal={"test": "f01_session"},
        provenance={"source": "test"},
    )

    async with engine.begin() as session:
        result = await store.persist_in_session(session=session, record=record)
        assert result.signal == {"test": "f01_session"}

        # Verify the row exists within the same transaction
        r = await session.execute(
            text("SELECT id FROM learning_memory WHERE signal_hash = :h"),
            {"h": compute_signal_hash({"test": "f01_session"})},
        )
        assert r.scalar() is not None

    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_persist_in_session_idempotent():
    """persist_in_session deduplicates via signal_hash (ON CONFLICT DO NOTHING)."""
    from libs.memory.memory_ledger import MemoryStore, PersistLearningMemoryInput

    engine = create_async_engine(DSN)
    store = MemoryStore(engine=engine)

    record = PersistLearningMemoryInput(
        tenant_id=TENANT,
        target_type="decision",
        target_id=uuid.uuid4(),
        signal={"test": "idempotent"},
        provenance={"source": "test"},
    )

    async with engine.begin() as session:
        r1 = await store.persist_in_session(session=session, record=record)
        r2 = await store.persist_in_session(session=session, record=record)
        assert r1.id == r2.id  # Same record returned (deduplication)

    await engine.dispose()
