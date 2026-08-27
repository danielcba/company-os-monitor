"""Architecture invariant tests for the Learning Loop (P7 feedback).

Enforces Cognitive Architecture rules (P1, P7, R1, R7, ADR-0002) for the
Learning Loop module as executable invariants.
"""
import ast
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

# Ensure libs is importable.
_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_root))

from libs.learning.learning_loop import compute_outcome_signal  # noqa: E402

LEARNING_LOOP_MODULE = Path("libs/learning/learning_loop.py")


# ---------------------------------------------------------------------------
# R1 — Exactly one cognitive capability: computes learning signal from outcomes.
# ---------------------------------------------------------------------------
def test_learning_loop_scope_is_single_capability():
    """R1: the learning loop module owns exactly one capability.

    It must not import action-layer execution/commit logic or write to stores.
    Checks actual code (not docstrings/comments) for forbidden patterns.
    """
    tree = ast.parse(LEARNING_LOOP_MODULE.read_text(encoding="utf-8"))
    # Collect all string literals (imports, assignments, function calls)
    code_strings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                code_strings.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                code_strings.append(node.module)
        elif isinstance(node, ast.Name):
            code_strings.append(node.id)
        elif isinstance(node, ast.Attribute):
            code_strings.append(node.attr)
    combined = " ".join(code_strings)
    forbidden = {"recommendation", "commit", "save_confidence", "insert_", "update_"}
    for word in forbidden:
        assert word not in combined, (
            f"R1 violated: {LEARNING_LOOP_MODULE.name} uses '{word}' in code"
        )


# ---------------------------------------------------------------------------
# P1 — Primacy of Observation: missing/unclear outcomes are NEVER fabricated.
# ---------------------------------------------------------------------------
def test_no_fabrication_of_missing_outcomes():
    """P1: decisions without actual outcomes yield None (inconclusive), never 0/1."""
    decision = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        expected_outcomes=[{"verifiable_by": "x", "prediction": 0.9}],
        actual_outcomes=None,
        confidence_id=uuid.uuid4(),
    )
    assert compute_outcome_signal(decision) is None


# ---------------------------------------------------------------------------
# ADR-0002 — external read/compute capability; no new persisted entity.
# ---------------------------------------------------------------------------
def test_learning_loop_is_read_compute_not_persisted():
    """ADR-0002: the learning loop must not define a new persisted table
    (no ORM __tablename__) nor a write engine — it is a computed view."""
    text = LEARNING_LOOP_MODULE.read_text(encoding="utf-8")
    assert "__tablename__" not in text, "ADR-0002 violated: new persisted entity"
    assert "create_async_engine" not in text, "ADR-0002 violated: write engine"
    assert "INSERT" not in text, "ADR-0002 violated: SQL INSERT"
    assert "UPDATE" not in text, "ADR-0002 violated: SQL UPDATE"
    # It must expose the learning loop capability.
    assert "def compute_outcome_signal" in text
    assert "def build_learning_history" in text
    assert "class LearningHistory" in text


# ---------------------------------------------------------------------------
# P7 — Learning through outcome: the module must compute ECE from outcomes.
# ---------------------------------------------------------------------------
def test_learning_loop_computes_ece():
    """P7: the learning loop must use ECE from calibration_model for feedback."""
    text = LEARNING_LOOP_MODULE.read_text(encoding="utf-8")
    assert "ece_score" in text, "P7 violated: ECE not computed"
    assert "historical_calibration" in text, "P7 violated: no calibration factor"
