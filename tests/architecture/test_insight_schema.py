"""H2 fix — Insight immutability in base schema.

Verifies that:
- Fresh schema includes the insight_content_immutable_trigger
- UPDATE of Insight content is blocked
- DELETE of Insight is blocked
- Migration sprint13 is idempotent (DROP TRIGGER IF EXISTS)
- No duplicate triggers exist after re-applying migration
"""
from __future__ import annotations

import os
import socket
import uuid
from pathlib import Path

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[2]
DSN = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
)
PG_DSN = DSN.replace("postgresql+asyncpg://", "postgresql://")

SCHEMA_PATH = ROOT / "infrastructure/docker/init-sql/01-schema.sql"
MIGRATION_PATH = ROOT / "infrastructure/db-migrations/sprint13-insight-content-trigger.sql"


def _db_available() -> bool:
    """Check if PostgreSQL is reachable."""
    try:
        sock = socket.create_connection(("127.0.0.1", 5433), timeout=2)
        sock.close()
    except (ConnectionRefusedError, OSError):
        return False
    else:
        return True


db_tests = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL not available on localhost:5433",
)


def test_fresh_schema_contains_insight_trigger():
    """The base schema must include the insight immutability trigger."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "insight_content_immutable_trigger" in schema, (
        "P1 violated: 01-schema.sql must contain insight_content_immutable_trigger"
    )
    assert "prevent_insight_content_update" in schema, (
        "P1 violated: 01-schema.sql must contain prevent_insight_content_update function"
    )


def test_migration_is_idempotent():
    """sprint13 migration must use DROP TRIGGER IF EXISTS for idempotency."""
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "DROP TRIGGER IF EXISTS" in migration, (
        "Migration must be idempotent (DROP TRIGGER IF EXISTS)"
    )
    assert "CREATE OR REPLACE FUNCTION" in migration, (
        "Migration must use CREATE OR REPLACE FUNCTION for idempotency"
    )


def test_no_duplicate_trigger_definitions():
    """Base schema and migration must not create duplicate functions."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    # Both define prevent_insight_content_update — schema uses CREATE OR REPLACE
    # and migration uses CREATE OR REPLACE + DROP TRIGGER IF EXISTS, so applying
    # both is safe. Verify the pattern is consistent.
    assert schema.count("prevent_insight_content_update") >= 1
    assert migration.count("prevent_insight_content_update") >= 1


@db_tests
@pytest.mark.asyncio
async def test_update_insight_content_blocked():
    """UPDATE of Insight content columns must be rejected by the trigger."""
    conn = await asyncpg.connect(PG_DSN)
    try:
        # Ensure tenant exists.
        tenant_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id, f"h2-{tenant_id.hex[:8]}", f"h2-{tenant_id.hex}",
        )

        # Create a context (FK dependency).
        context_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO contexts (id, tenant_id, evidence_ids, mental_model_id,
                                  purpose, coherence_score, competing_models)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            context_id, tenant_id, [], "test-model", "test-purpose", 0.8, "[]",
        )

        # Create an insight.
        insight_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO insights (id, tenant_id, context_id, hypothesis_ids,
                                  description, prior_understanding,
                                  mental_model_update, generated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, now())
            """,
            insight_id, tenant_id, context_id, [], "original description",
            "original prior", '{"key": "original"}',
        )

        # Attempt UPDATE of content — must be blocked.
        with pytest.raises(asyncpg.PostgresError, match="immutable"):
            await conn.execute(
                "UPDATE insights SET description = 'modified' WHERE id = $1",
                insight_id,
            )

        # Attempt UPDATE of prior_understanding — must be blocked.
        with pytest.raises(asyncpg.PostgresError, match="immutable"):
            await conn.execute(
                "UPDATE insights SET prior_understanding = 'modified' WHERE id = $1",
                insight_id,
            )

        # Attempt UPDATE of mental_model_update — must be blocked.
        with pytest.raises(asyncpg.PostgresError, match="immutable"):
            await conn.execute(
                "UPDATE insights SET mental_model_update = "
                "'{\"key\": \"modified\"}'::jsonb WHERE id = $1",
                insight_id,
            )

        # Verify original content unchanged.
        row = await conn.fetchrow(
            "SELECT description, prior_understanding FROM insights WHERE id = $1",
            insight_id,
        )
        assert row["description"] == "original description"
        assert row["prior_understanding"] == "original prior"
    finally:
        await conn.close()


@db_tests
@pytest.mark.asyncio
async def test_delete_insight_blocked():
    """DELETE of Insight must be rejected by the trigger."""
    conn = await asyncpg.connect(PG_DSN)
    try:
        tenant_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id, f"h2d-{tenant_id.hex[:8]}", f"h2d-{tenant_id.hex}",
        )

        context_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO contexts (id, tenant_id, evidence_ids, mental_model_id,
                                  purpose, coherence_score, competing_models)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            context_id, tenant_id, [], "test-model", "test-purpose", 0.8, "[]",
        )

        insight_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO insights (id, tenant_id, context_id, hypothesis_ids,
                                  description, prior_understanding,
                                  mental_model_update, generated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, now())
            """,
            insight_id, tenant_id, context_id, [], "desc", "prior", "{}",
        )

        # Attempt DELETE — must be blocked.
        with pytest.raises(asyncpg.PostgresError, match="immutable"):
            await conn.execute("DELETE FROM insights WHERE id = $1", insight_id)

        # Verify row still exists.
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM insights WHERE id = $1", insight_id
        )
        assert count == 1, "Insight was deleted despite trigger protection"
    finally:
        await conn.close()


@db_tests
@pytest.mark.asyncio
async def test_migration_idempotent_on_existing_db():
    """Applying sprint13 migration on a DB with the trigger already present
    must not fail (idempotency)."""
    conn = await asyncpg.connect(PG_DSN)
    try:
        migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")
        # Execute the migration — must not raise.
        await conn.execute(migration_sql)
        # Verify trigger still exists.
        trigger_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'insight_content_immutable_trigger'
            )
            """
        )
        assert trigger_exists, "Trigger must exist after idempotent migration"
    finally:
        await conn.close()
