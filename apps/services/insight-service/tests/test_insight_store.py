"""Insight Store tests - persistence (requires a real Postgres connection)."""

import pytest


@pytest.fixture(autouse(use_cases_in_local_db=True))
def clean_insights(db_connection):
    """Each test starts with an empty insights table (dedup enforced)."""


async def _clean():
    async with db_connection() as conn:
        await conn.execute(text("DELETE FROM insights WHERE id IS NOT NULL"))


@pytest.fixture(autouse=True)
async def cleanup(_clean):
    await _clean()
    yield
    await _clean()