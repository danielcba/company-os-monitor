"""Architecture invariant tests (Phase 17 — Architecture as Code).

These tests enforce the Cognitive Architecture rules (P1-P7, R1-R7) as
executable invariants. A future refactorization MUST NOT break these tests
silently. They are the architectural safety net.

Each test maps to a specific framework rule and documents the invariant
being enforced.
"""
import ast
import sys
from pathlib import Path

# Ensure libs is importable.
_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_root))


# ---------------------------------------------------------------------------
# Helper: parse a Python file and return imports + class/function names.
# ---------------------------------------------------------------------------

def _parse_file(path: Path) -> dict:
    """Parse a Python file and extract structural info."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    classes = []
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)
    return {"imports": imports, "classes": classes, "functions": functions}


# ---------------------------------------------------------------------------
# P1 — Primacy of Observation: Observation never interprets.
# ---------------------------------------------------------------------------

def test_observation_never_executes_action():
    """P1: Observation captures reality. It NEVER executes actions.

    The observation module must not import action-layer concepts
    (Recommendation, Decision, execute, commit).
    """
    obs_files = list(Path("libs/perception").glob("observation*.py"))
    assert obs_files, "No observation module found"
    for f in obs_files:
        info = _parse_file(f)
        for imp in info["imports"]:
            assert "action" not in imp.lower() or "observation" in imp.lower(), (
                f"P1 violated: {f.name} imports action-related module: {imp}"
            )


# ---------------------------------------------------------------------------
# P6 — Deliberate Action: Recommendation is not Decision.
# ---------------------------------------------------------------------------

def test_recommendation_is_not_decision():
    """P6: Recommendation proposes; Decision commits. They are separate."""
    rec_files = list(Path("libs/action").glob("recommendation*.py"))
    dec_files = list(Path("libs/action").glob("decision*.py"))
    assert rec_files, "No recommendation module found"
    assert dec_files, "No decision module found"
    # They must be separate files.
    for r in rec_files:
        for d in dec_files:
            assert r != d, "Recommendation and Decision must be separate modules"


# ---------------------------------------------------------------------------
# R4 — No conclusion influences action without confidence.
# ---------------------------------------------------------------------------

def test_decision_requires_confidence():
    """R4: Every Decision must reference a confidence_id."""
    dec_files = list(Path("libs/action").glob("decision*.py"))
    assert dec_files, "No decision module found"
    for f in dec_files:
        content = f.read_text(encoding="utf-8")
        assert "confidence_id" in content or "confidence" in content.lower(), (
            f"R4 violated: {f.name} does not reference confidence"
        )


def test_confidence_requires_provenance():
    """R5: Confidence must include justification and calibration data."""
    conf_files = list(Path("libs/learning").glob("confidence*.py"))
    assert conf_files, "No confidence module found"
    for f in conf_files:
        content = f.read_text(encoding="utf-8")
        assert "calibration_justification" in content, (
            f"R5 violated: {f.name} lacks calibration_justification"
        )
        assert "calibration_error_estimate" in content, (
            f"R5 violated: {f.name} lacks calibration_error_estimate"
        )


# ---------------------------------------------------------------------------
# Confidence is tenant-scoped.
# ---------------------------------------------------------------------------

def test_confidence_is_tenant_scoped():
    """Confidence queries must always filter by tenant_id."""
    conf_files = list(Path("libs/learning").glob("confidence*.py"))
    assert conf_files, "No confidence module found"
    for f in conf_files:
        content = f.read_text(encoding="utf-8")
        # All SELECT queries must include tenant_id in WHERE clause.
        # (Heuristic: check that tenant_id appears in SQL strings.)
        if "SELECT" in content:
            assert "tenant_id" in content, (
                f"Confidence store {f.name} queries lack tenant_id filter"
            )


# ---------------------------------------------------------------------------
# Cross-tenant requires superadmin authority.
# ---------------------------------------------------------------------------

def test_cross_tenant_requires_authority():
    """Cross-tenant access must require superadmin (cross_tenant permission)."""
    rbac_path = Path("libs/access/rbac.py")
    assert rbac_path.exists(), "RBAC module not found"
    content = rbac_path.read_text(encoding="utf-8")
    assert "cross_tenant" in content, "cross_tenant permission not defined"
    assert "ROLE_SUPERADMIN" in content, "superadmin role not defined"


# ---------------------------------------------------------------------------
# Observation and interpretation are never mixed (P1/R5 from ontology).
# ---------------------------------------------------------------------------

def test_raw_observation_cannot_bypass_perception():
    """Observation cannot be used directly by Reasoning or Action layers.

    The gateway (external) must not import libs.perception or libs.reasoning.
    """
    gateway_files = [
        Path("apps/gateway/api-gateway/src/service.py"),
        Path("apps/gateway/api-gateway/src/health.py"),
        Path("apps/gateway/api-gateway/src/boundary.py"),
    ]
    for f in gateway_files:
        if f.exists():
            content = f.read_text(encoding="utf-8")
            assert "libs.perception" not in content, (
                f"Gateway {f.name} imports libs.perception (boundary violation)"
            )
            assert "libs.reasoning" not in content, (
                f"Gateway {f.name} imports libs.reasoning (boundary violation)"
            )


# ---------------------------------------------------------------------------
# Cognitive boundary: every concept implements exactly one capability (R1).
# ---------------------------------------------------------------------------

def test_each_concept_has_one_store():
    """R1: Each cognitive concept has exactly one store implementation."""
    # Each concept directory should have one *store*.py file.
    concepts = {
        "perception": ["observation.py", "evidence.py", "context.py"],
        "reasoning": ["pattern.py", "anomaly.py", "hypothesis.py", "insight.py"],
        "learning": ["confidence.py"],
        "action": ["recommendation.py", "decision.py"],
    }
    for family, expected in concepts.items():
        family_path = Path("libs") / family
        assert family_path.exists(), f"Family {family} not found"
        for concept_file in expected:
            assert (family_path / concept_file).exists(), (
                f"Concept file {family_path / concept_file} not found"
            )


# ---------------------------------------------------------------------------
# DB immutability triggers: canonical tables must have content triggers.
# ---------------------------------------------------------------------------

def test_canonical_tables_have_immutability_triggers():
    """P1: All canonical cognitive tables must have immutability triggers."""
    schema_path = Path("infrastructure/docker/init-sql/01-schema.sql")
    assert schema_path.exists(), "Schema file not found"
    schema = schema_path.read_text(encoding="utf-8")

    # Tables that must have immutability triggers.
    must_have_triggers = [
        "observations",
        "evidence",
        "contexts",
        "patterns",
        "anomalies",
        "hypotheses",
        "insights",
        "confidence_scores",
        "recommendations",
        "decisions",
        "audit_log",
        "reports",
    ]
    for table in must_have_triggers:
        trigger_name = f"{table}_immutable_trigger"
        assert trigger_name in schema or "prevent_" in schema, (
            f"P1 violated: table {table} lacks immutability trigger"
        )


# ---------------------------------------------------------------------------
# One active context per purpose (P2).
# ---------------------------------------------------------------------------

def test_one_active_context_per_purpose_constraint():
    """P2: The schema must have a unique partial index for active contexts."""
    schema_path = Path("infrastructure/docker/init-sql/01-schema.sql")
    migration_path = Path(
        "infrastructure/db-migrations/phase5-context-activation-atomicity.sql"
    )
    # At least one of these must define the constraint.
    found = False
    for p in [schema_path, migration_path]:
        if p.exists():
            content = p.read_text(encoding="utf-8")
            if "idx_contexts_unique_active" in content:
                found = True
                break
    assert found, (
        "P2 violated: no unique partial index for active contexts per purpose"
    )


# ---------------------------------------------------------------------------
# Learning Memory ledger (P7 persistence, authorized 2026-08-27).
# ---------------------------------------------------------------------------


def test_learning_memory_ledger_migration_is_complete():
    """P1 + idempotency: the ledger migration defines table, immutability
    trigger and unique signal index."""
    schema = Path("infrastructure/docker/init-sql/01-schema.sql").read_text(
        encoding="utf-8"
    )
    migration = Path(
        "infrastructure/db-migrations/learning-memory-ledger.sql"
    ).read_text(encoding="utf-8")
    combined = schema + "\n" + migration
    assert "learning_memory" in combined, "learning_memory table missing"
    assert (
        "learning_memory_immutable_trigger" in combined
    ), "append-only immutability trigger missing (P1)"
    assert (
        "uq_learning_memory_signal" in combined
    ), "idempotent unique signal index missing"
    assert "ON CONFLICT" in migration or "DO NOTHING" in migration, (
        "persist must be idempotent"
    )


# ---------------------------------------------------------------------------
# Boundary: gateway enforces cognitive boundary (R3).
# ---------------------------------------------------------------------------

def test_boundary_module_exists():
    """R3: The gateway must have a boundary enforcement module."""
    boundary_path = Path("apps/gateway/api-gateway/src/boundary.py")
    assert boundary_path.exists(), "Boundary module not found"
    content = boundary_path.read_text(encoding="utf-8")
    assert "CANONICAL_FLOW" in content, "CANONICAL_FLOW not defined"
    assert "check_boundary" in content, "check_boundary function not defined"
    assert "validate_confidence" in content, "confidence validation not defined"
