"""Shared test infrastructure for H3 learning tests.

Provides:
- DB availability check (used by all DB-level test files)
- pytestmark for skipping DB tests when PostgreSQL is unavailable
"""
import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DSN = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
)


def _check_db_available() -> bool:
    """Check if PostgreSQL is reachable. Runs once at import time."""
    try:
        engine = create_async_engine(DSN)

        async def _check():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        asyncio.run(_check())
        asyncio.run(engine.dispose())
    except Exception:  # noqa: BLE001
        return False
    else:
        return True


db_available = _check_db_available()

pytestmark_db = pytest.mark.skipif(
    not db_available,
    reason="PostgreSQL unavailable — DB-level tests require a live database",
)
