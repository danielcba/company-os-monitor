"""Insight Store tests - persistence (requires a real Postgres connection).

Note: db_connection is a fixture provided by the test infrastructure
(PostgreSQL connection). Tests requiring Postgres cannot run without it.
"""

import libs  # noqa: F401
import pytest
from sqlalchemy import text


async def _clean_db(db_connection):
    async with db_connection() as conn:
        await conn.execute(text("DELETE FROM insights WHERE id IS NOT NULL"))


@pytest.fixture(autouse=True)
async def cleanup(db_connection):
    """Each test starts with an empty insights table (dedup enforced)."""
    await _clean_db(db_connection)
    yield
    await _clean_db(db_connection)
