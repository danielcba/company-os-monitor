"""Shared database utilities — engine factory for connection pooling.

Phase 8: Centralized DB engine management. All stores should receive an
engine from this factory instead of creating their own. This ensures:
- One engine per process
- One shared connection pool
- Consistent pool configuration
- No connection pool fragmentation

Configuration via environment variables:
- DATABASE_URL: PostgreSQL connection string
- DB_POOL_SIZE: Connection pool size (default: 20)
- DB_MAX_OVERFLOW: Max overflow connections (default: 40)
- DB_POOL_TIMEOUT: Seconds to wait for a connection (default: 30)
- DB_POOL_RECYCLE: Seconds before recycling a connection (default: 3600)
- DB_STATEMENT_TIMEOUT: Milliseconds for statement timeout (default: None)

Usage::

    from libs.shared.db import create_shared_engine

    engine = create_shared_engine()
    store = ConfidenceStore(engine=engine)
"""
import os

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_shared_engine(  # noqa: PLR0913,PLR0917 - configuration bundle
    dsn: str | None = None,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_timeout: int | None = None,
    pool_recycle: int | None = None,
    statement_timeout: int | None = None,
) -> AsyncEngine:
    """Create a shared async engine with production-ready pool settings.

    All stores in the process should share this engine. Creating multiple
    engines fragments the connection pool and can exhaust database connections.

    Pool limits:
    - pool_size=20: up to 20 persistent connections
    - max_overflow=40: up to 40 additional connections under burst
    - Total max: 60 connections per process

    Override via environment variables: DB_POOL_SIZE, DB_MAX_OVERFLOW,
    DB_POOL_TIMEOUT, DB_POOL_RECYCLE, DB_STATEMENT_TIMEOUT.
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
    if pool_timeout is None:
        pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    if pool_recycle is None:
        pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    if statement_timeout is None:
        raw = os.getenv("DB_STATEMENT_TIMEOUT")
        statement_timeout = int(raw) if raw else None

    connect_args: dict = {}
    if statement_timeout is not None:
        # asyncpg uses statement_timeout in milliseconds via connect_args.
        connect_args["command_timeout"] = statement_timeout / 1000.0

    return create_async_engine(
        dsn,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
        connect_args=connect_args if connect_args else {},
    )
