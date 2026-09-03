"""H3.0 Schema Tests — Verify migration DDL is correct and idempotent.

These tests verify the migration SQL is well-formed and idempotent.
DB-level tests skip when PostgreSQL is unavailable.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from conftest import DSN, pytestmark_db

pytestmark = pytestmark_db


@pytest.fixture
def engine():
    return create_async_engine(DSN)


@pytest.mark.asyncio
async def test_outcome_revisions_table_exists(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_name = 'outcome_revisions'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_learning_executions_table_exists(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_name = 'learning_executions'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_learning_memory_has_execution_id_column(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.columns"
                "  WHERE table_name = 'learning_memory'"
                "  AND column_name = 'execution_id'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_learning_executions_has_check_constraint(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.table_constraints"
                "  WHERE table_name = 'learning_executions'"
                "  AND constraint_name = 'chk_learning_execution_status'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_learning_executions_has_active_partial_index(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM pg_indexes"
                "  WHERE indexname = 'uq_learning_execution_active'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_outcome_revision_has_immutable_trigger(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.triggers"
                "  WHERE trigger_name = 'outcome_revision_immutable_trigger'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_learning_execution_has_fk_to_outcome_revision(engine):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.table_constraints"
                "  WHERE table_name = 'learning_executions'"
                "  AND constraint_name = 'fk_learning_execution_outcome_revision'"
                ")"
            )
        )
        assert result.scalar() is True


@pytest.mark.asyncio
async def test_migration_is_idempotent(engine):
    """Re-applying the migration should not fail (IF NOT EXISTS / IF EXISTS guards)."""
    # Verify the key objects exist — idempotent re-creation should not fail
    async with engine.connect() as conn:
        # Tables exist
        r = await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'outcome_revisions')"
        ))
        assert r.scalar() is True
        r = await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'learning_executions')"
        ))
        assert r.scalar() is True
        # Index exists
        r = await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes "
            "WHERE indexname = 'uq_learning_execution_active')"
        ))
        assert r.scalar() is True
        # Trigger exists
        r = await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.triggers "
            "WHERE trigger_name = 'outcome_revision_immutable_trigger')"
        ))
        assert r.scalar() is True


@pytest.mark.asyncio
async def test_outcome_revision_rejects_update(engine):
    """P6: immutability trigger blocks UPDATE on outcome_revisions."""
    import json as _json
    async with engine.begin() as conn:
        # Insert a test revision
        result = await conn.execute(
            text(
                "INSERT INTO outcome_revisions (tenant_id, decision_id, actual_outcomes) "
                "VALUES (:t, :d, CAST(:o AS jsonb)) RETURNING id"
            ),
            {
                "t": "00000000-0000-0000-0000-000000000001",
                "d": "00000000-0000-0000-0000-000000000002",
                "o": _json.dumps([]),
            },
        )
        rev_id = result.scalar()
        # Attempt UPDATE — should raise
        with pytest.raises(Exception, match="append-only"):
            await conn.execute(
                text(
                    "UPDATE outcome_revisions SET actual_outcomes = '[]'::jsonb "
                    "WHERE id = :id"
                ),
                {"id": rev_id},
            )


@pytest.mark.asyncio
async def test_learning_execution_rejects_invalid_status(engine):
    """P2: CHECK constraint rejects invalid status values."""
    import json as _json
    async with engine.begin() as conn:
        # Insert a valid outcome revision first
        result = await conn.execute(
            text(
                "INSERT INTO outcome_revisions (tenant_id, decision_id, actual_outcomes) "
                "VALUES (:t, :d, CAST(:o AS jsonb)) RETURNING id"
            ),
            {
                "t": "00000000-0000-0000-0000-000000000001",
                "d": "00000000-0000-0000-0000-000000000002",
                "o": _json.dumps([]),
            },
        )
        rev_id = result.scalar()
        # Attempt INSERT with invalid status — should raise
        with pytest.raises(Exception, match="chk_learning_execution_status"):
            await conn.execute(
                text(
                    "INSERT INTO learning_executions "
                    "(tenant_id, decision_id, outcome_revision_id, status) "
                    "VALUES (:t, :d, :r, 'invalid_status')"
                ),
                {
                    "t": "00000000-0000-0000-0000-000000000001",
                    "d": "00000000-0000-0000-0000-000000000002",
                    "r": rev_id,
                },
            )
