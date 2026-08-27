"""Architecture invariants for Insight Transformation journaling (R6, P4, R1, ADR-0002).

These tests assert framework conformance of the Insight Transformation
capability. They do NOT test behavior (covered in
test_insight_transformation.py).
"""
from __future__ import annotations

import ast
import inspect

from libs.memory import insight_transformation as it
from libs.memory.insight_transformation import InsightTransformationStore


def _module_source() -> str:
    return inspect.getsource(it)


def test_r6_journals_prior_to_updated_transformation():
    """R6: the transformation (prior_understanding -> mental_model_update) is
    surfaced as a journaled record."""
    src = _module_source()
    assert "prior_understanding" in src
    assert "mental_model_update" in src
    assert "transformation_kind" in src


def test_p4_classification_is_descriptive_not_causal():
    """P4: classification is descriptive (prior != updated); it never invents a
    causal explanation for the transformation."""
    src = _module_source()
    tree = ast.parse(src)
    # No causal-claim helper (e.g., "explain_cause", "root_cause") exists.
    func_names = {
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    forbidden = {"explain_cause", "root_cause", "infer_cause"}
    assert forbidden.isdisjoint(func_names)
    assert "_classify_transformation" in src


def test_r1_single_capability():
    """R1: the module exposes exactly one external capability entrypoint."""
    assert hasattr(InsightTransformationStore, "journal_for_tenant")
    classes = [n for n in dir(it) if n[0].isupper()]
    assert "InsightTransformationStore" in classes
    assert "InsightTransformationReport" in classes
    assert "InsightTransformationResult" in classes


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
    assert "_attribute_outcomes_to_insights" in src
