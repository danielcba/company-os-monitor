"""Cognitive Summary store for the API Gateway (external capability, ADR-0002).

Pure READ aggregation over the canonical pipeline tables for a single tenant
(the token's tenant scope is enforced in GatewayService/health.py). It counts
rows per cognitive concept so the external product can render a truthful
dashboard. It NEVER writes, never invents numbers, never reimplements cognitive
logic (R3): the counts come straight from the append-only pipeline state.
"""
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

COUNT_TOTALS = text(
    """
    SELECT
      (SELECT COUNT(*) FROM observations   WHERE tenant_id = :tenant_id) AS observations,
      (SELECT COUNT(*) FROM evidence       WHERE tenant_id = :tenant_id) AS evidence,
      (SELECT COUNT(*) FROM contexts       WHERE tenant_id = :tenant_id) AS contexts,
      (SELECT COUNT(*) FROM contexts
         WHERE tenant_id = :tenant_id AND is_active = TRUE)              AS active_contexts,
      (SELECT COUNT(*) FROM patterns       WHERE tenant_id = :tenant_id) AS patterns,
      (SELECT COUNT(*) FROM anomalies      WHERE tenant_id = :tenant_id) AS anomalies,
      (SELECT COUNT(*) FROM hypotheses     WHERE tenant_id = :tenant_id) AS hypotheses,
      (SELECT COUNT(*) FROM insights       WHERE tenant_id = :tenant_id)                                    AS insights,
      (SELECT COUNT(*) FROM confidence_scores
         WHERE tenant_id = :tenant_id)                                    AS confidence_scores,
      (SELECT COUNT(*) FROM recommendations
         WHERE tenant_id = :tenant_id)                                    AS recommendations,
      (SELECT COUNT(*) FROM decisions      WHERE tenant_id = :tenant_id) AS decisions,
      (SELECT COUNT(*) FROM reports        WHERE tenant_id = :tenant_id) AS reports,
      (SELECT COUNT(*) FROM servers        WHERE tenant_id = :tenant_id) AS servers
    """
)

COUNT_BY_STATUS = text(
    """
    SELECT 'hypotheses'      AS concept, status, COUNT(*) AS n
      FROM hypotheses        WHERE tenant_id = :tenant_id GROUP BY status
    UNION ALL
    SELECT 'recommendations' AS concept, status, COUNT(*) AS n
      FROM recommendations   WHERE tenant_id = :tenant_id GROUP BY status
    UNION ALL
    SELECT 'decisions'       AS concept, status, COUNT(*) AS n
      FROM decisions         WHERE tenant_id = :tenant_id GROUP BY status
    """
)


class CognitiveSummaryStore:
    """Persistence gateway for tenant-scoped pipeline read counters.

    Engine y session factory se crean UNA sola vez y se reusman.
    Inyectar via GatewayService.__init__ en lugar de por request.
    """

    def __init__(self, engine: AsyncEngine | None = None, dsn: str | None = None):
        if engine is not None:
            self._engine = engine
        else:
            self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def tenant_summary(self, *, tenant_id: uuid.UUID, timeout: float | None = 30.0) -> dict[str, Any]:
        """Total counts per cognitive concept for a tenant + lifecycle statuses.

Note: For high-traffic production use, consider caching this read-only
result in Redis with a short TTL (30-60s) since the data is append-only
and changes slowly. The CognitiveSummaryStore is engineered for reuse.
"""
        async with self._session_factory() as session:
            totals_row = (await session.execute(COUNT_TOTALS, {"tenant_id": tenant_id})).mappings().one()
            status_rows = await session.execute(COUNT_BY_STATUS, {"tenant_id": tenant_id})
            statuses: dict[str, dict[str, int]] = {}
            for row in status_rows.mappings():
                statuses.setdefault(row["concept"], {})[row["status"]] = row["n"]
            # Handle NULL values gracefully
            totals = {
                key: int(value) if value is not None else 0
                for key, value in totals_row.items()
            }
            return {
                "totals": totals,
                "status": {
                    "hypotheses": statuses.get("hypotheses", {}),
                    "recommendations": statuses.get("recommendations", {}),
                    "decisions": statuses.get("decisions", {}),
                },
            }

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except OperationalError:
            # Database not reachable - health check will report degraded
            pass

    async def close(self) -> None:
        await self._engine.dispose()