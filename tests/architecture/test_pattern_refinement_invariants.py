"""Architecture invariants for Pattern Refinement (P7, P4, R1, ADR-0002).

These tests assert framework conformance of the Pattern Refinement capability.
They do NOT test behavior (that is covered in test_pattern_refinement.py).
"""
from __future__ import annotations

import ast
import inspect

from libs.memory import pattern_refinement as pr
from libs.memory.pattern_refinement import PatternRefinementStore


def _module_source() -> str:
    return inspect.getsource(pr)


def test_p7_refinement_driven_by_decision_outcomes():
    """P7: patterns are refined from observed Decision outcomes."""
    src = _module_source()
    # The signal is derived from Decision actual_outcomes via consolidation.
    assert "actual_outcomes" in src
    assert "build_consolidation" in src


def test_p4_refinement_only_adjusts_support_never_invents_or_deletes():
    """P4: refinement adjusts support; it never invents or removes patterns."""
    src = _module_source()
    assert "DELETE" not in src
    assert "INSERT" not in src
    assert "CREATE TABLE" not in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in (
            "is_active",
            "strength_measure",
        ):
            assert not isinstance(node.ctx, ast.Store)


def test_r1_single_capability():
    """R1: the module exposes exactly one external capability entrypoint."""
    assert hasattr(PatternRefinementStore, "refine_for_tenant")
    classes = [n for n in dir(pr) if n[0].isupper()]
    assert "PatternRefinementStore" in classes
    assert "PatternRefinementReport" in classes
    assert "PatternRefinementResult" in classes


def test_adr0002_read_compute_no_new_persisted_entity_and_boundary():
    """ADR-0002: external read/compute capability; no new persisted entity;
    and the capability never pulls the reasoning/perception pipeline in."""
    src = _module_source()
    assert "__tablename__" not in src
    assert "Base.metadata" not in src
    assert "async def verify_connection" in src
    assert "INSERT" not in src and "UPDATE" not in src
    # The core must not import the forbidden pipeline packages.
    assert "libs.reasoning" not in src
    assert "libs.perception" not in src


def test_p1_no_fabrication_inconclusive_not_contradiction():
    """P1: missing/inconclusive outcomes are never counted as failures."""
    src = _module_source()
    # build_consolidation is the single source of truth for outcome verdict;
    # Pattern Refinement never defines its own classifier (which could fabricate
    # failures). It only forwards the consolidation verdicts.
    assert "build_consolidation" in src
    tree = ast.parse(src)
    func_names = {
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    forbidden = {"_classify", "classify", "_to_binary", "_compare_outcomes"}
    assert forbidden.isdisjoint(func_names)
    assert "_attribute_outcomes" in src
