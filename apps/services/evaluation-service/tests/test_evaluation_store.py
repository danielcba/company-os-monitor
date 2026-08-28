"""Integration tests for Evaluation persistence.

Requires the sandbox infra (postgres at 127.0.0.1:5433).
"""
import asyncio
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest

from libs.learning.confidence import ConfidenceStore, ConfidenceCreate, build_confidence
from libs.perception.evidence import EvidenceStore
from libs.perception.store import ObservationStore
from libs.reasoning.evaluation import (
    RESULT_CONFIRMED,
    RESULT_FALSIFIED,
    RESULT_INSUFFICIENT,
    EvaluationStore,
    create_evaluation,
)
from libs.reasoning.hypothesis import (
    HypothesisStore,
    STATUS_CANDIDATE,
    HypothesisCreate,
    build_hypothesis,
)

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"eval-{tenant_id}",
            f"evalslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute("DELETE FROM hypothesis_evaluations WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM hypotheses WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM confidence_scores WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM observations WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
        await conn.execute("SET session_replication_role = origin")
    finally:
        await conn.close()


@pytest.fixture
async def evaluation_store():
    instance = EvaluationStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def hypothesis_store():
    instance = HypothesisStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def confidence_store():
    instance = ConfidenceStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def observation_store():
    instance = ObservationStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


async def test_evaluation_insert_and_read_back(evaluation_store, hypothesis_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        # Create a hypothesis first
        hypothesis = build_hypothesis(
            HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=[uuid.uuid4()],
                pattern_ids=[uuid.uuid4()],
                description="A test hypothesis",
                predicted_consequences=["Consequence A", "Consequence B"],
                falsification_criterion="If X does not happen",
                coherence_score=0.5,
            )
        )
        await hypothesis_store.save_hypothesis(hypothesis)

        # Create evaluation (confidence_id can be NULL)
        evaluation = create_evaluation(
            tenant_id=tenant_id,
            hypothesis_id=hypothesis.id,
            evidence_ids=[uuid.uuid4(), uuid.uuid4()],
            observed_outcomes=[{"metric": "test", "value": 1}],
            support_count=2,
            contradiction_count=0,
            confidence_id=None,
            result=RESULT_CONFIRMED,
            rationale="Both predictions confirmed with high confidence",
        )
        row = await evaluation_store.save_evaluation(evaluation)
        assert row is not None
        assert row["id"] == evaluation.id
        assert row["result"] == RESULT_CONFIRMED
        assert row["support_count"] == 2

        # Read back
        evaluations = await evaluation_store.list_evaluations(tenant_id=tenant_id)
        assert len(evaluations) == 1
        assert evaluations[0].id == evaluation.id
        assert evaluations[0].result == RESULT_CONFIRMED
        assert evaluations[0].support_count == 2
        assert evaluations[0].rationale == "Both predictions confirmed with high confidence"
    finally:
        await _cleanup_tenant(tenant_id)


async def test_evaluation_save_is_idempotent(evaluation_store, hypothesis_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        hypothesis = build_hypothesis(
            HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=[uuid.uuid4()],
                pattern_ids=[uuid.uuid4()],
                description="Idempotent evaluation",
                predicted_consequences=["Consequence"],
                falsification_criterion="Criterion",
                coherence_score=0.5,
            )
        )
        await hypothesis_store.save_hypothesis(hypothesis)

        evaluation = create_evaluation(
            tenant_id=tenant_id,
            hypothesis_id=hypothesis.id,
            evidence_ids=[uuid.uuid4()],
            observed_outcomes=[],
            support_count=1,
            contradiction_count=0,
            confidence_id=None,
            result=RESULT_INSUFFICIENT,
            rationale="Insufficient evidence",
        )
        assert (await evaluation_store.save_evaluation(evaluation)) is not None
        assert (await evaluation_store.save_evaluation(evaluation)) is None
        assert await evaluation_store.evaluation_exists(id=evaluation.id) is True
    finally:
        await _cleanup_tenant(tenant_id)


async def test_evaluation_content_trigger_blocks_updates(evaluation_store, hypothesis_store):
    """Evaluation content is immutable - only INSERT allowed."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        hypothesis = build_hypothesis(
            HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=[uuid.uuid4()],
                pattern_ids=[uuid.uuid4()],
                description="Immutable evaluation",
                predicted_consequences=["Consequence"],
                falsification_criterion="Criterion",
                coherence_score=0.5,
            )
        )
        await hypothesis_store.save_hypothesis(hypothesis)

        evaluation = create_evaluation(
            tenant_id=tenant_id,
            hypothesis_id=hypothesis.id,
            evidence_ids=[uuid.uuid4()],
            observed_outcomes=[],
            support_count=1,
            contradiction_count=0,
            confidence_id=None,
            result=RESULT_INSUFFICIENT,
            rationale="Initial rationale",
        )
        await evaluation_store.save_evaluation(evaluation)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            # UPDATE should fail
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE hypothesis_evaluations SET rationale = 'changed' WHERE id = $1",
                    evaluation.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE hypothesis_evaluations SET result = 'confirmed' WHERE id = $1",
                    evaluation.id,
                )
            # DELETE should fail
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "DELETE FROM hypothesis_evaluations WHERE id = $1",
                    evaluation.id,
                )
        finally:
            await conn.close()
    finally:
        await _cleanup_tenant(tenant_id)


async def test_evaluation_list_by_hypothesis(evaluation_store, hypothesis_store):
    """Evaluations for a specific hypothesis can be retrieved."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        hypothesis = build_hypothesis(
            HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=[uuid.uuid4()],
                pattern_ids=[uuid.uuid4()],
                description="Hypothesis with multiple evaluations",
                predicted_consequences=["Consequence A", "Consequence B"],
                falsification_criterion="Falsification criterion",
                coherence_score=0.5,
            )
        )
        await hypothesis_store.save_hypothesis(hypothesis)

        # First evaluation - insufficient
        eval1 = create_evaluation(
            tenant_id=tenant_id,
            hypothesis_id=hypothesis.id,
            evidence_ids=[uuid.uuid4()],
            observed_outcomes=[{"metric": "test", "value": 1}],
            support_count=1,
            contradiction_count=0,
            confidence_id=None,
            result=RESULT_INSUFFICIENT,
            rationale="Only one prediction supported",
        )
        await evaluation_store.save_evaluation(eval1)

        # Second evaluation - confirmed (new evidence)
        eval2 = create_evaluation(
            tenant_id=tenant_id,
            hypothesis_id=hypothesis.id,
            evidence_ids=[uuid.uuid4(), uuid.uuid4()],
            observed_outcomes=[{"metric": "test", "value": 1}, {"metric": "test2", "value": 2}],
            support_count=2,
            contradiction_count=0,
            confidence_id=None,
            result=RESULT_CONFIRMED,
            rationale="Both predictions now confirmed",
        )
        await evaluation_store.save_evaluation(eval2)

        # Retrieve by hypothesis
        evaluations = await evaluation_store.list_evaluations_by_hypothesis(
            tenant_id=tenant_id, hypothesis_id=hypothesis.id
        )
        assert len(evaluations) == 2
        # Ordered by evaluated_at
        assert evaluations[0].result == RESULT_INSUFFICIENT
        assert evaluations[1].result == RESULT_CONFIRMED
        assert evaluations[0].rationale == "Only one prediction supported"
        assert evaluations[1].rationale == "Both predictions now confirmed"
    finally:
        await _cleanup_tenant(tenant_id)


async def test_evaluation_append_only_history(evaluation_store, hypothesis_store):
    """Multiple evaluations don't destroy previous ones (append-only)."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        hypothesis = build_hypothesis(
            HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=[uuid.uuid4()],
                pattern_ids=[uuid.uuid4()],
                description="History test hypothesis",
                predicted_consequences=["Consequence A", "Consequence B"],
                falsification_criterion="Falsification criterion",
                coherence_score=0.5,
            )
        )
        await hypothesis_store.save_hypothesis(hypothesis)

        # Create multiple evaluations over time
        for i, result in enumerate([RESULT_INSUFFICIENT, RESULT_INSUFFICIENT, RESULT_CONFIRMED]):
            eval_obj = create_evaluation(
                tenant_id=tenant_id,
                hypothesis_id=hypothesis.id,
                evidence_ids=[uuid.uuid4() for _ in range(i + 1)],
                observed_outcomes=[{"step": i}],
                support_count=i + 1,
                contradiction_count=0,
                confidence_id=None,
                result=result,
                rationale=f"Evaluation step {i + 1}",
            )
            await evaluation_store.save_evaluation(eval_obj)

        evaluations = await evaluation_store.list_evaluations_by_hypothesis(
            tenant_id=tenant_id, hypothesis_id=hypothesis.id
        )
        assert len(evaluations) == 3
        assert evaluations[0].result == RESULT_INSUFFICIENT
        assert evaluations[1].result == RESULT_INSUFFICIENT
        assert evaluations[2].result == RESULT_CONFIRMED
    finally:
        await _cleanup_tenant(tenant_id)


async def test_evaluation_tenant_isolation(evaluation_store, hypothesis_store):
    """Evaluations are tenant-scoped."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _create_tenant(tenant_a)
    await _create_tenant(tenant_b)
    try:
        # Hypothesis for tenant A
        hypothesis_a = build_hypothesis(
            HypothesisCreate(
                tenant_id=tenant_a,
                anomaly_ids=[uuid.uuid4()],
                pattern_ids=[uuid.uuid4()],
                description="Tenant A hypothesis",
                predicted_consequences=["A"],
                falsification_criterion="Not A",
                coherence_score=0.5,
            )
        )
        await hypothesis_store.save_hypothesis(hypothesis_a)

        # Evaluation for tenant A
        eval_a = create_evaluation(
            tenant_id=tenant_a,
            hypothesis_id=hypothesis_a.id,
            evidence_ids=[uuid.uuid4()],
            observed_outcomes=[],
            support_count=1,
            contradiction_count=0,
            confidence_id=None,
            result=RESULT_CONFIRMED,
            rationale="Tenant A",
        )
        await evaluation_store.save_evaluation(eval_a)

        # Query tenant B - should see nothing
        evaluations_b = await evaluation_store.list_evaluations(tenant_id=tenant_b)
        assert len(evaluations_b) == 0

        # Query tenant A - should see evaluation
        evaluations_a = await evaluation_store.list_evaluations(tenant_id=tenant_a)
        assert len(evaluations_a) == 1
        assert evaluations_a[0].rationale == "Tenant A"
    finally:
        await _cleanup_tenant(tenant_a)
        await _cleanup_tenant(tenant_b)


async def test_evaluation_re_evaluation_produces_new_row(evaluation_store, hypothesis_store):
    """Re-evaluating with new evidence produces a new evaluation row."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        hypothesis = build_hypothesis(
            HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=[uuid.uuid4()],
                pattern_ids=[uuid.uuid4()],
                description="Re-evaluation test",
                predicted_consequences=["Prediction A"],
                falsification_criterion="Not A",
                coherence_score=0.5,
            )
        )
        await hypothesis_store.save_hypothesis(hypothesis)

        # First evaluation
        eval1 = create_evaluation(
            tenant_id=tenant_id,
            hypothesis_id=hypothesis.id,
            evidence_ids=[uuid.uuid4()],
            observed_outcomes=[{"step": 1}],
            support_count=0,
            contradiction_count=0,
            confidence_id=None,
            result=RESULT_INSUFFICIENT,
            rationale="First evaluation",
        )
        row1 = await evaluation_store.save_evaluation(eval1)

        # Re-evaluation with new evidence
        eval2 = create_evaluation(
            tenant_id=tenant_id,
            hypothesis_id=hypothesis.id,
            evidence_ids=[uuid.uuid4(), uuid.uuid4()],  # Different evidence -> different id
            observed_outcomes=[{"step": 1}, {"step": 2}],
            support_count=1,
            contradiction_count=0,
            confidence_id=None,
            result=RESULT_CONFIRMED,
            rationale="Second evaluation with more evidence",
        )
        row2 = await evaluation_store.save_evaluation(eval2)
        assert row2 is not None  # Not a duplicate
        assert row2["id"] != row1["id"]  # Different id

        evaluations = await evaluation_store.list_evaluations_by_hypothesis(
            tenant_id=tenant_id, hypothesis_id=hypothesis.id
        )
        assert len(evaluations) == 2
    finally:
        await _cleanup_tenant(tenant_id)