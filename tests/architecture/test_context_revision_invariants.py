"""Architecture invariants for Context Revision (P7, P2, R1, ADR-0002).

These tests assert framework conformance of the Context Revision capability.
They do NOT test behavior (that is covered in test_context_revision.py).
"""
from __future__ import annotations

import ast
import inspect

from libs.memory import context_revision as cr
from libs.memory.context_revision import ContextRevisionStore


def _module_source() -> str:
    return inspect.getsource(cr)


def test_p7_revision_driven_by_decision_outcomes():
    """P7: contexts are revised from observed Decision outcomes."""
    src = _module_source()
    assert "actual_outcomes" in src
    assert "build_consolidation" in src


def test_p2_revision_only_suggests_never_activates():
    """P2: revision surfaces a competing model; it never activates/generates a
    Context."""
    src = _module_source()
    # No Context mutation / activation primitives.
    assert "INSERT" not in src
    assert "UPDATE" not in src
    assert "is_active" not in src.replace("ContextReadStore", "")
    # The result only *suggests* a competitor (no write path).
    assert "consider_competitor" in src
    assert "suggested_competitor" in src


def test_r1_single_capability():
    """R1: the module exposes exactly one external capability entrypoint."""
    assert hasattr(ContextRevisionStore, "revise_for_tenant")
    classes = [n for n in dir(cr) if n[0].isupper()]
    assert "ContextRevisionStore" in classes
    assert "ContextRevisionReport" in classes
    assert "ContextRevisionResult" in classes


def test_adr0002_read_compute_no_new_persisted_entity_and_boundary():
    """ADR-0002: external read/compute capability; no new persisted entity; and
    the capability never pulls the reasoning/perception pipeline in."""
    src = _module_source()
    assert "__tablename__" not in src
    assert "Base.metadata" not in src
    assert "async def verify_connection" in src
    assert "INSERT" not in src and "UPDATE" not in src
    assert "libs.reasoning" not in src
    assert "libs.perception" not in src


def test_p1_no_fabrication_inconclusive_not_contradiction():
    """P1: missing/inconclusive outcomes are never counted as failures."""
    src = _module_source()
    assert "build_consolidation" in src
    tree = ast.parse(src)
    func_names = {
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    forbidden = {"_classify", "classify", "_to_binary", "_compare_outcomes"}
    assert forbidden.isdisjoint(func_names)
    assert "_attribute_outcomes_to_contexts" in src
