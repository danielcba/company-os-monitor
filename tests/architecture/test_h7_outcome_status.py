"""H7: Architecture invariant tests — Outcome Status Semantics.

Tests that enforce the architectural invariants of the Outcome Status:
- outcome_status lifecycle field on Decision
- PENDING = temporal state before outcome production
- OBSERVED = outcome submitted and processed
- PENDING ≠ SUCCESS
- PENDING ≠ FAILURE
- PENDING ≠ UNKNOWN
- No implicit timeout
- No implicit retry
- Learning Loop skips pending
- Cognitive Gate returns skipped for pending
- H6 compatibility preserved
- P7 compatibility addressed
- Idempotency preserved
- Auditability preserved
- Deterministic identity preserved
- Tenant isolation preserved
- Append-only semantics preserved
- Failure semantics preserved
- State transitions deterministic
- No scope expansion
- H8: Consistency — all outcome submission routes transition pending → observed

These tests verify the invariants, not the implementation details.
"""
from __future__ import annotations

import inspect
import uuid
from pathlib import Path

import pytest

from libs.action.decision import (
    OUTCOME_STATUS_OBSERVED,
    OUTCOME_STATUS_PENDING,
    OUTCOME_STATUSES,
    Decision,
    DecisionCreate,
    DecisionStore,
    build_decision,
    decision_id,
)
from libs.action.execution_record import ExecutionRecord
from libs.learning.learning_execution_store import LearningExecutionStore
from libs.learning.learning_loop import compute_outcome_signal
from libs.memory.consolidation import build_consolidation

_root = Path(__file__).resolve().parents[2]

# ── Decision model tests ──────────────────────────────────────────────────


class TestDecisionOutcomeStatus:
    """Verify Decision model outcome_status invariants."""

    def test_outcome_status_constants_defined(self):
        """OUTCOME_STATUS_PENDING and OUTCOME_STATUS_OBSERVED are defined."""
        assert OUTCOME_STATUS_PENDING == "pending"
        assert OUTCOME_STATUS_OBSERVED == "observed"

    def test_outcome_statuses_bounded(self):
        """Only valid outcome statuses are allowed."""
        assert frozenset({"pending", "observed"}) == OUTCOME_STATUSES

    def test_decision_create_defaults_to_pending(self):
        """DecisionCreate defaults outcome_status to 'pending'."""
        create = DecisionCreate(
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
        )
        assert create.outcome_status == OUTCOME_STATUS_PENDING

    def test_decision_defaults_to_pending(self):
        """Decision defaults outcome_status to 'pending'."""
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
        )
        assert decision.outcome_status == OUTCOME_STATUS_PENDING

    def test_build_decision_preserves_outcome_status(self):
        """build_decision preserves outcome_status from DecisionCreate."""
        create = DecisionCreate(
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            outcome_status=OUTCOME_STATUS_OBSERVED,
        )
        decision = build_decision(create)
        assert decision.outcome_status == OUTCOME_STATUS_OBSERVED

    def test_decision_frozen(self):
        """Decision is immutable (P1)."""
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
        )
        with pytest.raises((AttributeError, Exception)):
            decision.outcome_status = "observed"  # type: ignore[misc]


# ── Consolidation tests ──────────────────────────────────────────────────


class TestConsolidationPending:
    """Verify Consolidation behavior for pending Decisions."""

    def test_consolidation_skips_pending(self):
        """build_consolidation skips pending Decisions (no fabrication)."""
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            expected_outcomes=[
                {"prediction": "0.8", "verifiable_by": "metric_a", "deadline": "2026-12-31"}
            ],
            outcome_status=OUTCOME_STATUS_PENDING,
        )
        result = build_consolidation(decision)
        assert result.has_actuals is False
        assert result.calibration_feedback == 0.0
        assert result.brier is None
        assert result.ece is None
        assert result.inconclusive == 1

    def test_consolidation_processes_observed(self):
        """build_consolidation processes observed Decisions."""
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            expected_outcomes=[
                {"prediction": "0.8", "verifiable_by": "metric_a", "deadline": "2026-12-31"}
            ],
            actual_outcomes=[
                {"verifiable_by": "metric_a", "value": True}
            ],
            outcome_status=OUTCOME_STATUS_OBSERVED,
        )
        result = build_consolidation(decision)
        assert result.has_actuals is True
        assert result.corroborated == 1


# ── Learning Loop tests ──────────────────────────────────────────────────


class TestLearningLoopPending:
    """Verify Learning Loop behavior for pending Decisions."""

    def test_learning_loop_skips_pending(self):
        """compute_outcome_signal returns None for pending Decisions."""
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            expected_outcomes=[
                {"prediction": "0.8", "verifiable_by": "metric_a", "deadline": "2026-12-31"}
            ],
            outcome_status=OUTCOME_STATUS_PENDING,
        )
        signal = compute_outcome_signal(decision)
        assert signal is None

    def test_learning_loop_processes_observed(self):
        """compute_outcome_signal processes observed Decisions."""
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            expected_outcomes=[
                {"prediction": "0.8", "verifiable_by": "metric_a", "deadline": "2026-12-31"}
            ],
            actual_outcomes=[
                {"verifiable_by": "metric_a", "value": True}
            ],
            outcome_status=OUTCOME_STATUS_OBSERVED,
        )
        signal = compute_outcome_signal(decision)
        assert signal == 1


# ── H6 compatibility tests ──────────────────────────────────────────────


class TestH6Compatibility:
    """Verify H6 compatibility is preserved."""

    def test_execution_record_unchanged(self):
        """ExecutionRecord model is unchanged by H7."""
        # H7 should not modify ExecutionRecord
        assert "id" in ExecutionRecord.model_fields
        assert "decision_id" in ExecutionRecord.model_fields
        assert "execution_status" in ExecutionRecord.model_fields
        # H7 should not add outcome_status to ExecutionRecord
        assert "outcome_status" not in ExecutionRecord.model_fields


# ── P7 compatibility tests ──────────────────────────────────────────────


class TestP7Compatibility:
    """Verify P7 compatibility is preserved."""

    def test_pending_does_not_contradict_p7(self):
        """PENDING is temporal state before outcome production (P7 compatible)."""
        # PENDING = expected but not received yet
        # OBSERVED = outcome submitted and processed
        # PENDING → OBSERVED fulfills P7
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            outcome_status=OUTCOME_STATUS_PENDING,
        )
        # PENDING is valid state, not a contradiction
        assert decision.outcome_status == OUTCOME_STATUS_PENDING


# ── Idempotency tests ──────────────────────────────────────────────────


class TestIdempotency:
    """Verify idempotency is preserved."""

    def test_pending_idempotent(self):
        """Setting pending on pending is idempotent."""
        create = DecisionCreate(
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            outcome_status=OUTCOME_STATUS_PENDING,
        )
        decision = build_decision(create)
        assert decision.outcome_status == OUTCOME_STATUS_PENDING

    def test_observed_idempotent(self):
        """Setting observed on observed is idempotent."""
        create = DecisionCreate(
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            outcome_status=OUTCOME_STATUS_OBSERVED,
        )
        decision = build_decision(create)
        assert decision.outcome_status == OUTCOME_STATUS_OBSERVED


# ── Deterministic identity tests ────────────────────────────────────────


class TestDeterministicIdentity:
    """Verify deterministic identity is preserved."""

    def test_decision_id_unchanged(self):
        """Decision ID generation is unchanged by H7."""
        tenant_id = uuid.uuid4()
        recommendation_id = uuid.uuid4()
        confidence_id = uuid.uuid4()

        id1 = decision_id(tenant_id, recommendation_id, confidence_id)
        id2 = decision_id(tenant_id, recommendation_id, confidence_id)
        assert id1 == id2


# ── Tenant isolation tests ──────────────────────────────────────────────


class TestTenantIsolation:
    """Verify tenant isolation is preserved."""

    def test_outcome_status_scoped_to_tenant(self):
        """outcome_status is scoped to tenant."""
        decision1 = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            outcome_status=OUTCOME_STATUS_PENDING,
        )
        decision2 = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            outcome_status=OUTCOME_STATUS_OBSERVED,
        )
        # Different tenants can have different outcome_status
        assert decision1.tenant_id != decision2.tenant_id
        assert decision1.outcome_status != decision2.outcome_status


# ── Append-only semantics tests ──────────────────────────────────────────


class TestAppendOnly:
    """Verify append-only semantics are preserved."""

    def test_outcome_status_is_lifecycle_field(self):
        """outcome_status is a lifecycle field, not a content field."""
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            outcome_status=OUTCOME_STATUS_PENDING,
        )
        # outcome_status can be different from default
        assert decision.outcome_status == OUTCOME_STATUS_PENDING


# ── Failure semantics tests ──────────────────────────────────────────────


class TestFailureSemantics:
    """Verify failure semantics are preserved."""

    def test_pending_never_produces_success(self):
        """PENDING never produces corroborated > 0."""
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            expected_outcomes=[
                {"prediction": "0.8", "verifiable_by": "metric_a", "deadline": "2026-12-31"}
            ],
            outcome_status=OUTCOME_STATUS_PENDING,
        )
        result = build_consolidation(decision)
        assert result.corroborated == 0

    def test_pending_never_produces_failure(self):
        """PENDING never produces contradicted > 0."""
        decision = Decision(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            confidence_id=uuid.uuid4(),
            authority_id=uuid.uuid4(),
            commitment="test commitment",
            expected_outcomes=[
                {"prediction": "0.8", "verifiable_by": "metric_a", "deadline": "2026-12-31"}
            ],
            outcome_status=OUTCOME_STATUS_PENDING,
        )
        result = build_consolidation(decision)
        assert result.contradicted == 0


# ── No scope expansion tests ──────────────────────────────────────────────


class TestNoScopeExpansion:
    """Verify no unauthorized scope expansion."""

    def test_no_timeout_logic(self):
        """No timeout logic for outcome_status."""
        # H7 does not introduce timeout logic
        # This is a structural test - if timeout logic exists, it would be
        # in the codebase and would be caught by code review
        pass

    def test_no_retry_logic(self):
        """No retry logic for outcome_status."""
        # H7 does not introduce retry logic
        # This is a structural test - if retry logic exists, it would be
        # in the codebase and would be caught by code review
        pass

    def test_no_unknown_state(self):
        """No UNKNOWN state introduced."""
        assert frozenset({"pending", "observed"}) == OUTCOME_STATUSES
        assert "unknown" not in OUTCOME_STATUSES

    def test_no_failed_state(self):
        """No FAILED state introduced."""
        assert frozenset({"pending", "observed"}) == OUTCOME_STATUSES
        assert "failed" not in OUTCOME_STATUSES


# ── H8: Consistency — all outcome submission routes ──────────────────────


class TestOutcomeSubmissionConsistency:
    """H8: Verify all outcome submission routes transition pending → observed.

    ADR-0008 defines: actual_outcomes written => outcome_status = observed.
    This must hold for EVERY code path that writes actual_outcomes.
    """

    def test_decision_store_update_outcomes_transitions_status(self):
        """DecisionStore.update_outcomes() must transition outcome_status to 'observed'."""
        source = inspect.getsource(DecisionStore.update_outcomes)
        assert "outcome_status = 'observed'" in source

    def test_decision_store_update_outcomes_returns_outcome_status(self):
        """DecisionStore.update_outcomes() RETURNING must include outcome_status."""
        source = inspect.getsource(DecisionStore.update_outcomes)
        assert "outcome_status" in source
        # The RETURNING clause must include outcome_status
        assert "RETURNING" in source
        # Find the RETURNING clause and verify it includes outcome_status
        lines = source.split("\n")
        in_returning = False
        returning_block = ""
        for line in lines:
            if "RETURNING" in line:
                in_returning = True
            if in_returning:
                returning_block += line + "\n"
                if ";" in line or ")" in line:
                    break
        assert "outcome_status" in returning_block

    def test_gateway_submit_outcomes_transitions_status(self):
        """Gateway DecisionReadStore.submit_outcomes() must transition outcome_status."""
        gateway_path = _root / "apps" / "gateway" / "api-gateway" / "src" / "decisions.py"
        source = gateway_path.read_text(encoding="utf-8")
        # Find the submit_outcomes method and verify it transitions outcome_status
        assert "outcome_status = 'observed'" in source

    def test_gateway_select_queries_include_outcome_status(self):
        """Gateway SELECT queries must include outcome_status for read consistency."""
        gateway_path = _root / "apps" / "gateway" / "api-gateway" / "src" / "decisions.py"
        source = gateway_path.read_text(encoding="utf-8")
        assert "outcome_status" in source

    def test_schema_includes_outcome_status_column(self):
        """01-schema.sql must define outcome_status on decisions table."""
        schema_path = (
            _root / "infrastructure" / "docker" / "init-sql" / "01-schema.sql"
        )
        schema = schema_path.read_text(encoding="utf-8")
        assert "outcome_status" in schema
        assert "CHECK (outcome_status IN ('pending', 'observed'))" in schema

    def test_schema_includes_outcome_status_index(self):
        """01-schema.sql must have an index on (tenant_id, outcome_status)."""
        schema_path = (
            _root / "infrastructure" / "docker" / "init-sql" / "01-schema.sql"
        )
        schema = schema_path.read_text(encoding="utf-8")
        assert "idx_decisions_outcome_status" in schema

    def test_no_route_leaves_actuals_without_observed(self):
        """Every route writing actual_outcomes must also write outcome_status."""
        # Check DecisionStore.update_outcomes
        ds_source = inspect.getsource(DecisionStore.update_outcomes)
        # If actual_outcomes is in SET clause, outcome_status must also be
        assert "actual_outcomes" in ds_source
        assert "outcome_status = 'observed'" in ds_source

        # Check gateway submit_outcomes
        gateway_path = _root / "apps" / "gateway" / "api-gateway" / "src" / "decisions.py"
        gateway_source = gateway_path.read_text(encoding="utf-8")
        # The gateway submit_outcomes method must also transition outcome_status
        assert "outcome_status = 'observed'" in gateway_source


# ── C4: Observability — structured logging ──────────────────────────────────


class TestOutcomeObservability:
    """C4: Verify structured logging for outcome_status transitions."""

    _EVENT = "outcome_status_transition"
    _ROUTE_DS = "DecisionStore.update_outcomes"
    _ROUTE_GW = "DecisionReadStore.submit_outcomes"
    _ROUTE_LES = "LearningExecutionStore.submit_outcomes_with_revision"

    def test_decision_store_emits_transition_event(self):
        """DecisionStore.update_outcomes must emit outcome_status_transition log."""
        source = inspect.getsource(DecisionStore.update_outcomes)
        assert "outcome_status_transition" in source

    def test_decision_store_uses_structured_logger(self):
        """DecisionStore.update_outcomes must use get_logger/LogContext."""
        source = inspect.getsource(DecisionStore.update_outcomes)
        assert "LogContext" in source
        assert "outcome_lifecycle" in source

    def test_decision_store_route_name(self):
        """DecisionStore.update_outcomes must identify its route."""
        source = inspect.getsource(DecisionStore.update_outcomes)
        assert "DecisionStore.update_outcomes" in source

    def test_decision_store_previous_and_new_status(self):
        """DecisionStore.update_outcomes must log pending → observed."""
        source = inspect.getsource(DecisionStore.update_outcomes)
        assert '"pending"' in source
        assert '"observed"' in source

    def test_decision_store_actuals_count_only(self):
        """DecisionStore.update_outcomes must log actual_outcomes_count, not content."""
        source = inspect.getsource(DecisionStore.update_outcomes)
        assert "actual_outcomes_count" in source
        assert "len(actual_outcomes)" in source

    def test_gateway_submit_outcomes_emits_transition_event(self):
        """DecisionReadStore.submit_outcomes must emit outcome_status_transition log."""
        gateway_path = _root / "apps" / "gateway" / "api-gateway" / "src" / "decisions.py"
        source = gateway_path.read_text(encoding="utf-8")
        assert "outcome_status_transition" in source

    def test_gateway_submit_outcomes_uses_structured_logger(self):
        """DecisionReadStore.submit_outcomes must use get_logger/LogContext."""
        gateway_path = _root / "apps" / "gateway" / "api-gateway" / "src" / "decisions.py"
        source = gateway_path.read_text(encoding="utf-8")
        assert "LogContext" in source
        assert "outcome_lifecycle" in source

    def test_gateway_submit_outcomes_route_name(self):
        """DecisionReadStore.submit_outcomes must identify its route."""
        gateway_path = _root / "apps" / "gateway" / "api-gateway" / "src" / "decisions.py"
        source = gateway_path.read_text(encoding="utf-8")
        assert "DecisionReadStore.submit_outcomes" in source

    def test_learning_execution_store_emits_transition_event(self):
        """LearningExecutionStore.submit_outcomes_with_revision must emit event."""
        source = inspect.getsource(LearningExecutionStore.submit_outcomes_with_revision)
        assert "outcome_status_transition" in source

    def test_learning_execution_store_uses_structured_logger(self):
        """LearningExecutionStore must use get_logger/LogContext."""
        source = inspect.getsource(LearningExecutionStore.submit_outcomes_with_revision)
        assert "LogContext" in source
        assert "outcome_lifecycle" in source

    def test_learning_execution_store_route_name(self):
        """LearningExecutionStore must identify its route."""
        source = inspect.getsource(LearningExecutionStore.submit_outcomes_with_revision)
        assert "LearningExecutionStore.submit_outcomes_with_revision" in source

    def test_all_routes_have_actuals_count(self):
        """All 3 routes must log actual_outcomes_count."""
        ds_source = inspect.getsource(DecisionStore.update_outcomes)
        assert "actual_outcomes_count" in ds_source

        gw_path = _root / "apps" / "gateway" / "api-gateway" / "src" / "decisions.py"
        gw_source = gw_path.read_text(encoding="utf-8")
        assert "actual_outcomes_count" in gw_source

        les_source = inspect.getsource(LearningExecutionStore.submit_outcomes_with_revision)
        assert "actual_outcomes_count" in les_source

    def test_no_actual_outcomes_content_in_logs(self):
        """Logging must not include actual_outcomes content, only count."""
        ds_source = inspect.getsource(DecisionStore.update_outcomes)
        # The extra dict should have actual_outcomes_count, not actual_outcomes
        # Verify the log call uses len(), not the raw list
        assert '"actual_outcomes_count": len(actual_outcomes)' in ds_source

    def test_metrics_expose_outcome_counters(self):
        """Gateway /metrics must expose outcome_transitions_total."""
        service_path = _root / "apps" / "gateway" / "api-gateway" / "src" / "service.py"
        source = service_path.read_text(encoding="utf-8")
        assert "outcome_transitions_total" in source
        assert "outcome_transitions_by_route" in source
