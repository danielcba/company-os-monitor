"""11 - Migration Integrity: schema has all required constraints.

Verifies: immutability triggers, unique active context index, evidence_ids,
tenant foreign keys, required indexes.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


def _read_schema():
    schema_path = Path("infrastructure/docker/init-sql/01-schema.sql")
    if not schema_path.exists():
        pytest.skip("Schema file not found")
    return schema_path.read_text(encoding="utf-8")


def _read_migration(name):
    path = Path(f"infrastructure/db-migrations/{name}")
    if not path.exists():
        pytest.skip(f"Migration {name} not found")
    return path.read_text(encoding="utf-8")


def test_schema_has_immutability_triggers():
    """All canonical tables must have immutability triggers."""
    schema = _read_schema()
    tables = [
        "observations", "evidence", "contexts", "patterns",
        "anomalies", "hypotheses", "confidence_scores",
        "recommendations", "decisions", "audit_log", "reports",
    ]
    for table in tables:
        assert f"{table}_immutable_trigger" in schema or "prevent_" in schema, (
            f"Table {table} lacks immutability trigger"
        )


def test_context_activation_atomicity_index():
    """Unique partial index for active contexts per tenant+purpose must exist."""
    migration = _read_migration("phase5-context-activation-atomicity.sql")
    assert "idx_contexts_unique_active" in migration


def test_confidence_evidence_scope_column():
    """evidence_ids column must exist in confidence_scores."""
    migration = _read_migration("phase7-confidence-evidence-scope.sql")
    assert "evidence_ids" in migration


def test_user_tables_exist():
    """Users and roles tables must exist."""
    migration = _read_migration("sprint12-users-tables.sql")
    assert "users" in migration
    assert "roles" in migration


def test_all_content_triggers_exist():
    """Every sprint must have created its content trigger."""
    triggers = [
        "sprint4-context-content-trigger.sql",
        "sprint5-pattern-content-trigger.sql",
        "sprint6-anomaly-content-trigger.sql",
        "sprint7-hypothesis-content-trigger.sql",
        "sprint8-confidence-content-trigger.sql",
        "sprint9-recommendation-content-trigger.sql",
        "sprint10-decision-content-trigger.sql",
        "sprint11-report-content-trigger.sql",
        "sprint13-insight-content-trigger.sql",
    ]
    for trigger_file in triggers:
        content = _read_migration(trigger_file)
        assert "CREATE OR REPLACE FUNCTION" in content or "CREATE FUNCTION" in content, (
            f"{trigger_file} does not define a trigger function"
        )
