"""12 - SQL Tenant Leak: verify tenant isolation in SQL queries.

All store queries must filter by tenant_id.
"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


def test_confidence_store_queries_includes_tenant():
    """ConfidenceStore SELECT queries must include tenant_id filter."""
    from libs.learning.confidence import SELECT_CONFIDENCE, SELECT_LATEST_BY_TARGET
    assert "tenant_id" in str(SELECT_LATEST_BY_TARGET)
    assert "tenant_id" in str(SELECT_CONFIDENCE)


def test_context_store_set_active_includes_tenant():
    """ContextStore.set_active must require tenant_id."""
    from libs.perception.context import ContextStore
    sig = inspect.signature(ContextStore.set_active)
    assert "tenant_id" in sig.parameters


def test_decision_store_update_outcomes_includes_tenant():
    """DecisionStore.update_outcomes must include tenant_id."""
    from libs.action.decision import DecisionStore
    source = inspect.getsource(DecisionStore.update_outcomes)
    assert "tenant_id" in source


def test_confidence_store_requires_tenant():
    """ConfidenceStore.get_confidence must require tenant_id."""
    from libs.learning.confidence import ConfidenceStore
    sig = inspect.signature(ConfidenceStore.get_confidence)
    assert "tenant_id" in sig.parameters


def test_decision_store_requires_tenant():
    """DecisionStore.list_decisions must require tenant_id."""
    from libs.action.decision import DecisionStore
    sig = inspect.signature(DecisionStore.list_decisions)
    assert "tenant_id" in sig.parameters


def test_observation_store_requires_tenant():
    """ObservationStore.list_observations must require tenant_id."""
    from libs.perception.store import ObservationStore
    sig = inspect.signature(ObservationStore.list_observations)
    assert "tenant_id" in sig.parameters
