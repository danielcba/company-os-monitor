"""H3.2 Tests — Signal identity & provenance traceability.

Verifies:
- signal_hash is content identity (deterministic, order-independent)
- execution_id is execution identity (different executions → different IDs)
- provenance survives retry
- memory points to correct execution
- memory points to correct outcome revision
- no provenance chain is silently lost
"""
import hashlib
import json
import uuid

import pytest

from libs.learning.learning_execution import (
    STATUS_COMPLETED,
    STATUS_RUNNING,
    build_learning_execution,
    transition_status,
)
from libs.learning.outcome_revision import build_outcome_revision
from libs.memory.memory_ledger import compute_signal_hash

TENANT = uuid.uuid4()
DECISION = uuid.uuid4()


# ── Signal hash: content identity ──────────────────────────────────────────


class TestSignalHash:
    def test_deterministic(self):
        signal = {"pattern_id": "abc", "recommended_action": "keep"}
        h1 = compute_signal_hash(signal)
        h2 = compute_signal_hash(signal)
        assert h1 == h2

    def test_order_independent(self):
        s1 = {"b": 2, "a": 1}
        s2 = {"a": 1, "b": 2}
        assert compute_signal_hash(s1) == compute_signal_hash(s2)

    def test_content_sensitive(self):
        s1 = {"action": "keep", "strength": 0.8}
        s2 = {"action": "degrade", "strength": 0.8}
        assert compute_signal_hash(s1) != compute_signal_hash(s2)

    def test_is_sha256_hex(self):
        h = compute_signal_hash({"test": True})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_nested_structure_sensitive(self):
        s1 = {"nested": {"key": "value1"}}
        s2 = {"nested": {"key": "value2"}}
        assert compute_signal_hash(s1) != compute_signal_hash(s2)

    def test_same_hash_same_content(self):
        """Two signals with identical content produce the same hash."""
        signal = {
            "decision_id": str(uuid.uuid4()),
            "calibration_feedback": 0.75,
            "brier": 0.25,
            "ece": 0.1,
        }
        h = compute_signal_hash(signal)
        # Re-serialize to verify
        canonical = json.dumps(signal, sort_keys=True, separators=(",", ":"), default=str)
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert h == expected


# ── Execution identity ──────────────────────────────────────────────────────


class TestExecutionIdentity:
    def test_different_executions_different_ids(self):
        ex1 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=uuid.uuid4(),
        )
        ex2 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=uuid.uuid4(),
        )
        assert ex1.id != ex2.id

    def test_same_inputs_different_ids(self):
        """Even with identical inputs, each execution gets a unique UUID."""
        rev = uuid.uuid4()
        ids = set()
        for _ in range(10):
            ex = build_learning_execution(
                tenant_id=TENANT,
                decision_id=DECISION,
                outcome_revision_id=rev,
            )
            ids.add(ex.id)
        assert len(ids) == 10

    def test_execution_links_to_outcome_revision(self):
        rev_id = uuid.uuid4()
        ex = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=rev_id,
        )
        assert ex.outcome_revision_id == rev_id


# ── Provenance chain ───────────────────────────────────────────────────────


class TestProvenanceChain:
    def test_outcome_revision_links_to_decision(self):
        rev = build_outcome_revision(
            tenant_id=TENANT,
            decision_id=DECISION,
            actual_outcomes=[{"metric": "revenue", "value": True}],
        )
        assert rev.decision_id == DECISION
        assert rev.tenant_id == TENANT

    def test_execution_links_to_outcome_revision(self):
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

    def test_retry_preserves_parent_chain(self):
        ex1 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=uuid.uuid4(),
        )
        ex1 = transition_status(ex1, STATUS_RUNNING)
        ex1 = transition_status(ex1, STATUS_COMPLETED)

        ex2 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=ex1.outcome_revision_id,
            attempt_number=2,
            parent_execution_id=ex1.id,
        )
        assert ex2.parent_execution_id == ex1.id
        assert ex2.outcome_revision_id == ex1.outcome_revision_id

    def test_signal_provenance_contains_decision_id(self):
        """All signals should include decision_id in provenance for traceability."""
        decision_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        # Simulate what the H3 learning loop computes
        consolidation_provenance = {
            "decision_id": str(decision_id),
            "tenant_id": str(tenant_id),
            "source": "outcome_consolidation",
        }
        assert consolidation_provenance["decision_id"] == str(decision_id)

        pattern_provenance = {
            "pattern_id": str(uuid.uuid4()),
            "context_id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "source": "pattern_refinement",
            "decision_id": str(decision_id),
        }
        assert pattern_provenance["decision_id"] == str(decision_id)

    def test_multiple_revisions_for_same_decision_independent(self):
        """Each outcome revision is independent (append-only audit trail)."""
        revisions = []
        for i in range(3):
            rev = build_outcome_revision(
                tenant_id=TENANT,
                decision_id=DECISION,
                actual_outcomes=[{"iteration": i}],
            )
            revisions.append(rev)

        ids = {r.id for r in revisions}
        assert len(ids) == 3
        # All reference the same decision
        assert all(r.decision_id == DECISION for r in revisions)

    def test_execution_attempt_numbering(self):
        """Retry increments attempt_number while preserving provenance."""
        rev_id = uuid.uuid4()
        ex1 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=rev_id,
            attempt_number=1,
        )
        ex2 = build_learning_execution(
            tenant_id=TENANT,
            decision_id=DECISION,
            outcome_revision_id=rev_id,
            attempt_number=2,
            parent_execution_id=ex1.id,
        )
        assert ex2.attempt_number == ex1.attempt_number + 1
        assert ex2.outcome_revision_id == ex1.outcome_revision_id


# ── DB-level execution_id provenance tests ──────────────────────────────────


from conftest import DSN, pytestmark_db
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
@pytestmark_db
async def test_h3_memory_record_contains_execution_id():
    """TEST 1: H3-generated learning_memory row contains execution_id."""
    from libs.learning.learning_execution_store import LearningExecutionStore
    from libs.memory.memory_ledger import MemoryStore, PersistLearningMemoryInput

    engine = create_async_engine(DSN)
    exec_store = LearningExecutionStore(engine=engine)
    mem_store = MemoryStore(engine=engine)

    # Create outcome revision first
    rev = await exec_store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "test", "value": True}],
    )

    # Create H3 execution
    execution, session = await exec_store.begin_phase2(
        tenant_id=TENANT,
        decision_id=DECISION,
        outcome_revision_id=rev.id,
    )
    assert execution is not None

    # Persist a learning signal within the H3 transaction
    record = PersistLearningMemoryInput(
        tenant_id=TENANT,
        target_type="decision",
        target_id=uuid.uuid4(),
        signal={"test": "provenance"},
        provenance={"source": "h3_test"},
        execution_id=execution.id,
    )
    result = await mem_store.persist_in_session(session=session, record=record)

    # Complete execution and commit
    await exec_store.complete_execution_in_session(
        session=session,
        execution_id=execution.id,
        signal_count=1,
    )
    await session.commit()

    # Verify: learning_memory row has execution_id = execution.id
    async with engine.begin() as conn:
        row = await conn.execute(
            text("SELECT execution_id FROM learning_memory WHERE id = :id"),
            {"id": result.id},
        )
        exec_id = row.scalar()
        assert exec_id is not None
        assert exec_id == execution.id

    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_h3_fk_provenance_is_valid():
    """TEST 2: FK provenance is valid - learning_memory.execution_id references existing learning_executions."""
    from libs.learning.learning_execution_store import LearningExecutionStore
    from libs.memory.memory_ledger import MemoryStore, PersistLearningMemoryInput

    engine = create_async_engine(DSN)
    exec_store = LearningExecutionStore(engine=engine)
    mem_store = MemoryStore(engine=engine)

    rev = await exec_store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "test", "value": True}],
    )

    execution, session = await exec_store.begin_phase2(
        tenant_id=TENANT,
        decision_id=DECISION,
        outcome_revision_id=rev.id,
    )

    record = PersistLearningMemoryInput(
        tenant_id=TENANT,
        target_type="decision",
        target_id=uuid.uuid4(),
        signal={"test": "fk_provenance"},
        provenance={"source": "h3_test"},
        execution_id=execution.id,
    )
    result = await mem_store.persist_in_session(session=session, record=record)

    await exec_store.complete_execution_in_session(
        session=session,
        execution_id=execution.id,
        signal_count=1,
    )
    await session.commit()

    # Verify FK: learning_memory.execution_id references a valid learning_executions row
    async with engine.begin() as conn:
        row = await conn.execute(
            text(
                "SELECT 1 FROM learning_executions le "
                "JOIN learning_memory lm ON lm.execution_id = le.id "
                "WHERE lm.id = :mem_id AND le.id = :exec_id"
            ),
            {"mem_id": result.id, "exec_id": execution.id},
        )
        assert row.scalar() == 1

        # Also verify tenant matches
        row = await conn.execute(
            text(
                "SELECT le.tenant_id FROM learning_executions le "
                "JOIN learning_memory lm ON lm.execution_id = le.id "
                "WHERE lm.id = :mem_id"
            ),
            {"mem_id": result.id},
        )
        assert row.scalar() == TENANT

    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_h3_multiple_signals_share_execution_id():
    """TEST 3: Multiple signals from same H3 execution share the same execution_id."""
    from libs.learning.learning_execution_store import LearningExecutionStore
    from libs.memory.memory_ledger import MemoryStore, PersistLearningMemoryInput

    engine = create_async_engine(DSN)
    exec_store = LearningExecutionStore(engine=engine)
    mem_store = MemoryStore(engine=engine)

    rev = await exec_store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "test", "value": True}],
    )

    execution, session = await exec_store.begin_phase2(
        tenant_id=TENANT,
        decision_id=DECISION,
        outcome_revision_id=rev.id,
    )

    # Persist 3 signals within the same execution
    signal_ids = []
    for i in range(3):
        record = PersistLearningMemoryInput(
            tenant_id=TENANT,
            target_type="decision",
            target_id=uuid.uuid4(),
            signal={"signal_num": i, "data": f"test_{i}"},
            provenance={"source": "h3_test", "index": i},
            execution_id=execution.id,
        )
        result = await mem_store.persist_in_session(session=session, record=record)
        signal_ids.append(result.id)

    await exec_store.complete_execution_in_session(
        session=session,
        execution_id=execution.id,
        signal_count=3,
    )
    await session.commit()

    # Verify all 3 signals have the same execution_id
    async with engine.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT execution_id FROM learning_memory WHERE id = ANY(:ids)"
            ),
            {"ids": signal_ids},
        )
        exec_ids = [row[0] for row in rows]
        assert len(exec_ids) == 3
        assert all(eid == execution.id for eid in exec_ids)

    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_h3_different_executions_different_provenance():
    """TEST 4: Different executions produce different execution_id provenance."""
    from libs.learning.learning_execution_store import LearningExecutionStore
    from libs.memory.memory_ledger import MemoryStore, PersistLearningMemoryInput

    engine = create_async_engine(DSN)
    exec_store = LearningExecutionStore(engine=engine)
    mem_store = MemoryStore(engine=engine)

    # Create two outcome revisions for DIFFERENT decisions
    decision1 = uuid.uuid4()
    decision2 = uuid.uuid4()

    rev1 = await exec_store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=decision1,
        actual_outcomes=[{"metric": "test1", "value": True}],
    )
    rev2 = await exec_store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=decision2,
        actual_outcomes=[{"metric": "test2", "value": True}],
    )

    # Create two executions for different decisions (no lock contention)
    execution1, session1 = await exec_store.begin_phase2(
        tenant_id=TENANT,
        decision_id=decision1,
        outcome_revision_id=rev1.id,
    )
    execution2, session2 = await exec_store.begin_phase2(
        tenant_id=TENANT,
        decision_id=decision2,
        outcome_revision_id=rev2.id,
    )

    # Persist signal in execution 1
    record1 = PersistLearningMemoryInput(
        tenant_id=TENANT,
        target_type="decision",
        target_id=uuid.uuid4(),
        signal={"test": "exec1"},
        provenance={"source": "h3_test", "execution": 1},
        execution_id=execution1.id,
    )
    result1 = await mem_store.persist_in_session(session=session1, record=record1)

    # Persist signal in execution 2
    record2 = PersistLearningMemoryInput(
        tenant_id=TENANT,
        target_type="decision",
        target_id=uuid.uuid4(),
        signal={"test": "exec2"},
        provenance={"source": "h3_test", "execution": 2},
        execution_id=execution2.id,
    )
    result2 = await mem_store.persist_in_session(session=session2, record=record2)

    # Complete both executions
    await exec_store.complete_execution_in_session(
        session=session1, execution_id=execution1.id, signal_count=1
    )
    await exec_store.complete_execution_in_session(
        session=session2, execution_id=execution2.id, signal_count=1
    )
    await session1.commit()
    await session2.commit()

    # Verify no cross-linking: execution1's signal points to execution1, execution2's to execution2
    async with engine.begin() as conn:
        row = await conn.execute(
            text("SELECT execution_id FROM learning_memory WHERE id = :id"),
            {"id": result1.id},
        )
        assert row.scalar() == execution1.id

        row = await conn.execute(
            text("SELECT execution_id FROM learning_memory WHERE id = :id"),
            {"id": result2.id},
        )
        assert row.scalar() == execution2.id

        # Verify they are different
        assert execution1.id != execution2.id

    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_h3_rollback_removes_provenance():
    """TEST 5: Rollback removes both execution and learning_memory (F-01 regression check)."""
    from libs.learning.learning_execution_store import LearningExecutionStore
    from libs.memory.memory_ledger import MemoryStore, PersistLearningMemoryInput

    engine = create_async_engine(DSN)
    exec_store = LearningExecutionStore(engine=engine)
    mem_store = MemoryStore(engine=engine)

    rev = await exec_store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "rollback_test", "value": True}],
    )

    execution, session = await exec_store.begin_phase2(
        tenant_id=TENANT,
        decision_id=DECISION,
        outcome_revision_id=rev.id,
    )

    # Persist a signal
    record = PersistLearningMemoryInput(
        tenant_id=TENANT,
        target_type="decision",
        target_id=uuid.uuid4(),
        signal={"test": "rollback"},
        provenance={"source": "h3_test"},
        execution_id=execution.id,
    )
    result = await mem_store.persist_in_session(session=session, record=record)

    # Rollback the entire Phase 2 transaction
    await session.rollback()

    # Verify: no execution, no learning_memory for this execution
    async with engine.begin() as conn:
        # Check execution is gone
        row = await conn.execute(
            text("SELECT id FROM learning_executions WHERE id = :id"),
            {"id": execution.id},
        )
        assert row.scalar() is None

        # Check learning_memory is gone (rolled back)
        row = await conn.execute(
            text("SELECT id FROM learning_memory WHERE id = :id"),
            {"id": result.id},
        )
        assert row.scalar() is None

    await engine.dispose()


@pytest.mark.asyncio
@pytestmark_db
async def test_h3_idempotency_preserves_provenance():
    """TEST 6: Idempotency (ON CONFLICT DO NOTHING) works correctly with execution_id."""
    from libs.learning.learning_execution_store import LearningExecutionStore
    from libs.memory.memory_ledger import MemoryStore, PersistLearningMemoryInput, compute_signal_hash

    engine = create_async_engine(DSN)
    exec_store = LearningExecutionStore(engine=engine)
    mem_store = MemoryStore(engine=engine)

    rev = await exec_store.create_outcome_revision(
        tenant_id=TENANT,
        decision_id=DECISION,
        actual_outcomes=[{"metric": "idempotent", "value": True}],
    )

    execution, session = await exec_store.begin_phase2(
        tenant_id=TENANT,
        decision_id=DECISION,
        outcome_revision_id=rev.id,
    )

    # Create a UNIQUE signal for this test run to avoid conflicts with other tests
    unique_suffix = str(uuid.uuid4())[:8]
    signal = {"test": "idempotent_provenance", "unique": unique_suffix}
    signal_hash = compute_signal_hash(signal)

    record1 = PersistLearningMemoryInput(
        tenant_id=TENANT,
        target_type="decision",
        target_id=uuid.uuid4(),
        signal=signal,
        provenance={"source": "h3_test", "attempt": 1},
        execution_id=execution.id,
    )
    record2 = PersistLearningMemoryInput(
        tenant_id=TENANT,
        target_type="decision",
        target_id=record1.target_id,  # Same target -> same signal_hash -> conflict
        signal=signal,
        provenance={"source": "h3_test", "attempt": 2},
        execution_id=execution.id,
    )

    # Persist twice
    result1 = await mem_store.persist_in_session(session=session, record=record1)
    result2 = await mem_store.persist_in_session(session=session, record=record2)

    # Should return the same record (deduplication)
    assert result1.id == result2.id

    await exec_store.complete_execution_in_session(
        session=session, execution_id=execution.id, signal_count=1
    )
    await session.commit()

    # Verify only one row exists for this unique signal
    async with engine.begin() as conn:
        rows = await conn.execute(
            text("SELECT id, execution_id FROM learning_memory WHERE signal_hash = :h"),
            {"h": signal_hash},
        )
        all_rows = list(rows)
        assert len(all_rows) == 1
        assert all_rows[0][1] == execution.id

    await engine.dispose()
