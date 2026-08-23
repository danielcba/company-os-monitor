"""Shared database utilities — engine factory for connection pooling."""
import os

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_shared_engine(
    dsn: str | None = None,
    pool_size: int | None = None,
    max_overflow: int | None = None,
) -> AsyncEngine:
    """Create a shared async engine with production-ready pool settings.

    Default pool_size=20, max_overflow=40, pool_pre_ping=True, pool_recycle=3600.
    Override via environment variables: DB_POOL_SIZE, DB_MAX_OVERFLOW.
    """
    if dsn is None:
        dsn = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
        )
    if pool_size is None:
        pool_size = int(os.getenv("DB_POOL_SIZE", "20"))
    if max_overflow is None:
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "40"))

    return create_async_engine(
        dsn,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
