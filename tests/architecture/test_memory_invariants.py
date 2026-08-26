"""Architecture invariant tests for the Memory (P7) Outcome Consolidation.

Enforces Cognitive Architecture rules (P1, R1, R7, ADR-0002) for the new
Memory read/compute capability as executable invariants. A future
refactorization MUST NOT break these silently.

Each test maps to a specific framework rule and documents the invariant.
"""
import ast
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure libs is importable.
_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_root))

from libs.memory.consolidation import (  # noqa: E402
    CrossTenantConsolidationError,
    build_consolidation,
    consolidate_decisions,
)

MEMORY_MODULE = Path("libs/memory/consolidation.py")


# ---------------------------------------------------------------------------
# R1 — Exactly one cognitive capability: only consolidates outcomes.
# It must not import action-layer decision/execution concepts nor implement
# calibration/decision/execution logic itself.
# ---------------------------------------------------------------------------
def test_memory_scope_is_single_capability():
    """R1: the consolidation module owns exactly one capability (consolidation).

    It must not import execution/commit/recommendation logic from the action
    layer (it only reads the Decision schema to compare expected vs actual).
    """
    info = _parse_file(MEMORY_MODULE)
    forbidden = {"recommendation", "execute", "commit"}
    for imp in info["imports"]:
        low = imp.lower()
        # allowed: libs.action.decision (read schema) and confidence/calibration
        if any(f in low for f in forbidden) and "decision" not in low:
            pytest.fail(f"R1 violated: {MEMORY_MODULE.name} imports {imp}")


# ---------------------------------------------------------------------------
# P1 — Primacy of Observation: missing/unclear actuals are NEVER fabricated
# into a failure/contradiction.
# ---------------------------------------------------------------------------
def test_no_fabrication_of_missing_actuals():
    """P1: a Decision with no actual outcomes yields an INCONCLUSIVE result,
    never a contradiction/failure."""
    decision = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        expected_outcomes=[
            {"verifiable_by": "x", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=None,
    )
    result = build_consolidation(decision)
    assert result.contradicted == 0
    assert result.corroborated == 0
    assert result.inconclusive == 1
    assert result.calibration_feedback == 0.0


def test_no_fabrication_of_unparseable_actuals():
    """P1: an actual outcome we cannot interpret is inconclusive, not failed."""
    decision = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        expected_outcomes=[
            {"verifiable_by": "x", "prediction": 0.9, "deadline": "2026-09-01"}
        ],
        actual_outcomes=[{"verifiable_by": "x", "value": "indeterminate"}],
    )
    result = build_consolidation(decision)
    assert result.contradicted == 0
    assert result.inconclusive == 1


# ---------------------------------------------------------------------------
# Tenant scope — consolidation never mixes tenants.
# ---------------------------------------------------------------------------
def test_consolidation_enforces_tenant_scope():
    """Tenant isolation: a cross-tenant batch is rejected (defense in depth)."""
    tenant = uuid.uuid4()
    other = uuid.uuid4()
    decisions = [
        SimpleNamespace(
            id=uuid.uuid4(), tenant_id=tenant,
            expected_outcomes=[], actual_outcomes=[],
        ),
        SimpleNamespace(
            id=uuid.uuid4(), tenant_id=other,
            expected_outcomes=[], actual_outcomes=[],
        ),
    ]
    try:
        consolidate_decisions(tenant, decisions)
        pytest.fail("cross-tenant consolidation was NOT rejected")
    except CrossTenantConsolidationError:
        pass


# ---------------------------------------------------------------------------
# ADR-0002 — external read/compute capability; no new persisted entity.
# ---------------------------------------------------------------------------
def test_memory_is_read_compute_not_persisted():
    """ADR-0002: the consolidation module must not define a new persisted table
    (no ORM __tablename__) nor a write engine — it is a computed view."""
    text = MEMORY_MODULE.read_text(encoding="utf-8")
    assert "__tablename__" not in text, "ADR-0002 violated: new persisted entity"
    assert "create_async_engine" not in text, "ADR-0002 violated: write engine"
    assert "create_engine" not in text, "ADR-0002 violated: write engine"
    # It must expose the consolidation capability.
    assert "def consolidate_decisions" in text
    assert "class ConsolidationStore" in text


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _parse_file(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return {"imports": imports}
