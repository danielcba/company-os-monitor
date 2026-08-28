"""Observation persistence - append-only INSERT into the Postgres observations table.

P1 enforcement: Observations are immutable. This store only performs INSERTs;
the database trigger blocks any UPDATE/DELETE on the observations table.
"""
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from libs.cognitive_core.observation_bus import Observation

INSERT_OBSERVATION = text(
    """
    INSERT INTO observations (
        id, tenant_id, source_id, source_type, fact_type, fact_value,
        unit, captured_at, quality_class, raw_payload
    )
    VALUES (
        :id, :tenant_id, :source_id, :source_type, :fact_type,
        CAST(:fact_value AS jsonb), :unit, :captured_at, :quality_class,
        CAST(:raw_payload AS jsonb)
    )
    RETURNING id, tenant_id, fact_type, captured_at, quality_class
    """
)

CHECK_OBSERVATION_EXISTS = text(
    "SELECT 1 FROM observations WHERE id = :id AND captured_at = :captured_at"
)

SELECT_OBSERVATIONS = text(
    """
    SELECT id, tenant_id, source_id, source_type, fact_type, fact_value,
           unit, captured_at, quality_class, raw_payload
    FROM observations
    WHERE tenant_id = :tenant_id
    ORDER BY captured_at, id
    LIMIT :limit OFFSET :offset
    """
)

SELECT_OBSERVATIONS_SINCE = text(
    """
    SELECT id, tenant_id, source_id, source_type, fact_type, fact_value,
           unit, captured_at, quality_class, raw_payload
    FROM observations
    WHERE tenant_id = :tenant_id AND captured_at >= :since
    ORDER BY captured_at, id
    LIMIT :limit
    """
)


class ObservationStore:
    """Persistence gateway for the Evidence Store (PostgreSQL observations table)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    @staticmethod
    def _as_json(value: dict[str, Any]) -> str:
        return json.dumps(value, default=str)

    async def save_observation(self, observation: Observation) -> dict[str, Any]:
        """Insert one immutable observation. Returns the persisted row."""
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_OBSERVATION,
                {
                    "id": observation.id,
                    "tenant_id": observation.tenant_id,
                    "source_id": observation.source_id,
                    "source_type": observation.source_type,
                    "fact_type": observation.fact_type,
                    "fact_value": self._as_json(observation.fact_value),
                    "unit": observation.unit,
                    "captured_at": observation.captured_at,
                    "quality_class": observation.quality_class,
                    "raw_payload": self._as_json(observation.raw_payload),
                },
            )
            await session.commit()
            return dict(result.mappings().one())

    async def observation_exists(
        self, *, id: uuid.UUID, captured_at: datetime
    ) -> bool:
        """Check existence (used to avoid duplicating observations on retries)."""
        async with self._session_factory() as session:
            result = await session.execute(
                CHECK_OBSERVATION_EXISTS,
                {"id": id, "captured_at": captured_at},
            )
            return result.scalar() is not None

    async def list_observations(
        self, *, tenant_id: uuid.UUID, limit: int = 500, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Read-only load of the immutable observation rows for a tenant.

        Exposed for the Report service (Sprint 11): the Technical report's
        Evidence Chain renders the observations that back each evidence row.
        This is a plain READ (P1: observations are never written here) - the
        service never touches the observation bus (Redis).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_OBSERVATIONS,
                {"tenant_id": tenant_id, "limit": limit, "offset": offset},
            )
            rows = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["fact_value"], str):
                    row["fact_value"] = json.loads(row["fact_value"])
                if isinstance(row["raw_payload"], str):
                    row["raw_payload"] = json.loads(row["raw_payload"])
                rows.append(row)
            return rows

    async def list_observations_since(
        self, *, tenant_id: uuid.UUID, since: datetime, limit: int = 1000
    ) -> list[dict[str, Any]]:
        """Read-only load of observations since a given timestamp.

        Used by the Evaluation Service to get new evidence for hypothesis evaluation.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_OBSERVATIONS_SINCE,
                {"tenant_id": tenant_id, "since": since, "limit": limit},
            )
            rows = []
            for mapping in result.mappings():
                row = dict(mapping)
                if isinstance(row["fact_value"], str):
                    row["fact_value"] = json.loads(row["fact_value"])
                if isinstance(row["raw_payload"], str):
                    row["raw_payload"] = json.loads(row["raw_payload"])
                rows.append(row)
            return rows

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()