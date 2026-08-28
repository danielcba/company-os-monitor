"""Tests for Learning Loop failure semantics.

Verifies that the system distinguishes:
- outcome accepted + learning completed
- outcome accepted + learning failed
- outcome accepted + learning pending
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.access.rbac import ROLE_ADMIN
from libs.access.security import JwtService

# Import from the gateway app's module
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "gateway" / "api-gateway"))
from src.health import GatewayServer
from src.service import GatewayService

SECRET = "dev-secret-key"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
USER_ADMIN = "00000000-0000-0000-0000-0000000000aa"


class FakeDecisionReadStore:
    """Fake decision read store that simulates outcome submission."""

    def __init__(self):
        self.decisions = {}

    async def submit_outcomes(self, *, tenant_id, decision_id, actual_outcomes, executed_at):
        decision = {
            "id": str(decision_id),
            "tenant_id": str(tenant_id),
            "status": "completed",
            "actual_outcomes": actual_outcomes,
        }
        self.decisions[str(decision_id)] = decision
        return {"decision": decision, "status": "outcomes_submitted"}


class FailingLearningLoopStore:
    """Learning loop store that always fails."""

    async def run_for_decision(self, *, tenant_id, decision_id):
        raise RuntimeError("Simulated learning loop failure")

    async def verify_connection(self):
        return None


class WorkingLearningLoopStore:
    """Learning loop store that works."""

    def __init__(self):
        self.call_count = 0

    async def run_for_decision(self, *, tenant_id, decision_id):
        self.call_count += 1
        from types import SimpleNamespace

        from libs.memory.consolidation import ConsolidationResult
        from libs.memory.context_revision import ContextRevisionReport
        from libs.memory.insight_transformation import InsightTransformationReport
        from libs.memory.pattern_refinement import PatternRefinementReport

        consolidation = ConsolidationResult(
            decision_id=decision_id,
            tenant_id=tenant_id,
            has_actuals=True,
            expected_count=1,
            actual_count=1,
            corroborated=1,
            contradicted=0,
            inconclusive=0,
            calibration_feedback=1.0,
            details=[],
        )
        pattern_refinement = PatternRefinementReport(tenant_id=tenant_id, total_patterns=0, patterns_with_outcomes=0, results=[])
        context_revision = ContextRevisionReport(tenant_id=tenant_id, total_contexts=0, contexts_with_outcomes=0, results=[])
        insight_transformation = InsightTransformationReport(tenant_id=tenant_id, total_insights=0, results=[])
        return SimpleNamespace(
            tenant_id=tenant_id,
            decision_id=decision_id,
            consolidation=consolidation,
            pattern_refinement=pattern_refinement,
            context_revision=context_revision,
            insight_transformation=insight_transformation,
            persisted=[],
        )

    async def verify_connection(self):
        return None


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


@pytest.fixture
async def client_with_failing_loop(jwt):
    decision_store = FakeDecisionReadStore()
    learning_loop_store = FailingLearningLoopStore()
    service = GatewayService(
        jwt,
        decision_read_store=decision_store,
        learning_loop_store=learning_loop_store,
    )
    server = GatewayServer(service, jwt)
    from aiohttp.test_utils import TestClient, TestServer
    tc = TestClient(TestServer(server.app))
    await tc.start_server()
    yield tc
    await tc.close()


@pytest.fixture
async def client_with_working_loop(jwt):
    decision_store = FakeDecisionReadStore()
    learning_loop_store = WorkingLearningLoopStore()
    service = GatewayService(
        jwt,
        decision_read_store=decision_store,
        learning_loop_store=learning_loop_store,
    )
    server = GatewayServer(service, jwt)
    from aiohttp.test_utils import TestClient, TestServer
    tc = TestClient(TestServer(server.app))
    await tc.start_server()
    yield tc, learning_loop_store
    await tc.close()


@pytest.fixture
async def client_without_loop(jwt):
    decision_store = FakeDecisionReadStore()
    service = GatewayService(
        jwt,
        decision_read_store=decision_store,
        learning_loop_store=None,
    )
    server = GatewayServer(service, jwt)
    from aiohttp.test_utils import TestClient, TestServer
    tc = TestClient(TestServer(server.app))
    await tc.start_server()
    yield tc
    await tc.close()


def _token(jwt, *, tenant_id=TENANT_A):
    return jwt.create_access_token(
        user_id=USER_ADMIN, tenant_id=tenant_id, email="a@x.test", role=ROLE_ADMIN
    )


def _hdr(jwt, **kw):
    return {"Authorization": f"Bearer {_token(jwt, **kw)}", "Content-Type": "application/json"}


async def test_learning_loop_completed_status(client_with_working_loop, jwt):
    """Outcome accepted + learning completed -> learning_loop.status == 'completed'."""
    tc, store = client_with_working_loop
    decision_id = str(uuid.uuid4())
    body = {"actual_outcomes": [{"verifiable_by": "metric1", "value": True}]}
    resp = await tc.post(
        f"/api/v1/tenants/{TENANT_A}/decisions/{decision_id}/outcomes",
        headers=_hdr(jwt), json=body,
    )
    assert resp.status == 200
    result = await resp.json()
    assert result["status"] == "outcomes_submitted"
    assert "learning_loop" in result
    assert result["learning_loop"]["status"] == "completed"
    assert "consolidation_feedback" in result["learning_loop"]
    assert store.call_count == 1


async def test_learning_loop_failed_status(client_with_failing_loop, jwt):
    """Outcome accepted + learning failed -> learning_loop.status == 'failed'."""
    tc = client_with_failing_loop
    decision_id = str(uuid.uuid4())
    body = {"actual_outcomes": [{"verifiable_by": "metric1", "value": True}]}
    resp = await tc.post(
        f"/api/v1/tenants/{TENANT_A}/decisions/{decision_id}/outcomes",
        headers=_hdr(jwt), json=body,
    )
    assert resp.status == 200
    result = await resp.json()
    assert result["status"] == "outcomes_submitted"
    assert "learning_loop" in result
    assert result["learning_loop"]["status"] == "failed"
    assert "error" in result["learning_loop"]


async def test_learning_loop_pending_status(client_without_loop, jwt):
    """Outcome accepted + learning pending -> learning_loop.status == 'pending'."""
    tc = client_without_loop
    decision_id = str(uuid.uuid4())
    body = {"actual_outcomes": [{"verifiable_by": "metric1", "value": True}]}
    resp = await tc.post(
        f"/api/v1/tenants/{TENANT_A}/decisions/{decision_id}/outcomes",
        headers=_hdr(jwt), json=body,
    )
    assert resp.status == 200
    result = await resp.json()
    assert result["status"] == "outcomes_submitted"
    assert "learning_loop" in result
    assert result["learning_loop"]["status"] == "pending"
    assert "reason" in result["learning_loop"]


async def test_outcome_submission_succeeds_even_when_learning_fails(client_with_failing_loop, jwt):
    """Outcome submission succeeds even when learning loop fails (decoupled)."""
    tc = client_with_failing_loop
    decision_id = str(uuid.uuid4())
    body = {"actual_outcomes": [{"verifiable_by": "metric1", "value": True}]}
    resp = await tc.post(
        f"/api/v1/tenants/{TENANT_A}/decisions/{decision_id}/outcomes",
        headers=_hdr(jwt), json=body,
    )
    # Outcome submission should succeed (200) even though learning failed
    assert resp.status == 200
    result = await resp.json()
    assert result["status"] == "outcomes_submitted"
    # But learning_loop status should indicate failure
    assert result["learning_loop"]["status"] == "failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])