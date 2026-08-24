"""Phase 12 — Tenant Scoping de Todos los Stores tests."""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.action.decision import DecisionStore
from libs.learning.confidence import SELECT_LATEST_BY_TARGET, ConfidenceStore
from libs.perception.context import SET_CONTEXT_ACTIVE, ContextStore


def test_confidence_select_latest_includes_tenant():
    """Phase 12: SELECT_LATEST_BY_TARGET must include tenant_id filter."""
    sql = str(SELECT_LATEST_BY_TARGET)
    assert "tenant_id = :tenant_id" in sql


def test_context_set_active_includes_tenant():
    """Phase 12: SET_CONTEXT_ACTIVE must include tenant_id filter."""
    sql = str(SET_CONTEXT_ACTIVE)
    assert "tenant_id = :tenant_id" in sql


def test_decision_update_outcomes_includes_tenant():
    """Phase 12: update_outcomes dynamic SQL must include tenant_id filter."""
    source = inspect.getsource(DecisionStore.update_outcomes)
    assert "tenant_id = :tenant_id" in source


def test_context_set_active_requires_tenant():
    """Phase 12: set_active method signature must include tenant_id."""
    sig = inspect.signature(ContextStore.set_active)
    assert "tenant_id" in sig.parameters


def test_decision_update_outcomes_requires_tenant():
    """Phase 12: update_outcomes method signature must include tenant_id."""
    sig = inspect.signature(DecisionStore.update_outcomes)
    assert "tenant_id" in sig.parameters


def test_confidence_get_confidence_requires_tenant():
    """Phase 12: get_confidence method signature must include tenant_id."""
    sig = inspect.signature(ConfidenceStore.get_confidence)
    assert "tenant_id" in sig.parameters
