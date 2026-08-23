"""Base class for read stores with shared verify_connection/close."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


class BaseReadStore:
    """Base class providing shared engine lifecycle for gateway read stores."""

    def __init__(self, dsn: str | None = None, engine: AsyncEngine | None = None):
        if engine is not None:
            self._engine = engine
        else:
            self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        """Dispose the engine's connection pool."""
        await self._engine.dispose()
