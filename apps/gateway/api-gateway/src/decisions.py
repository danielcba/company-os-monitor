"""Decision READ/WRITE store for the API Gateway (external capability, ADR-0002).

Pure READ of the decisions table (P1) for a single tenant (the token's tenant
scope is enforced in GatewayService/health.py). A Decision is a commitment to a
course of action (Action · Commit): it records the definitive ``commitment``,
the falsifiable ``expected_outcomes`` (prediction + verifiable_by + deadline,
stated BEFORE execution), the ``authority_id`` under which it was taken, the
declared ``risk_tolerance`` and the calibrated Confidence that supported it
(R4). Content is immutable (P1, enforced by the content trigger); only
``status`` (committed -> executing/completed/rolled_back), ``executed_at`` and
``actual_outcomes`` are lifecycle fields populated by the Learning loop (future
sprints) — the expected vs actual comparison is the primary learning signal of
the system ("A decision ends deliberation. It does not end learning.").

This store pages, filters and sorts the committed decisions and resolves the
desglose for one row: the specific Recommendation being committed (with its
leading hypothesis desglose) and the specific calibrated Confidence row that
supports the commitment. It also provides an endpoint to submit actual outcomes
after decision execution, which populates ``actual_outcomes`` and ``executed_at``
through the DecisionStore's ``update_outcomes`` method. It NEVER writes content
columns (blocked by the content trigger) and never executes actions.

New POST /api/v1/tenants/{tenant_id}/decisions/{decision_id}/outcomes:
  Submits actual outcomes for a decision, populating ``actual_outcomes`` and
  ``executed_at``. The comparison expected vs actual is the primary learning
  signal (P7).
"""
import json
import uuid
from datetime import datetime
from typing import Any

from libs.shared.facets_cache import FacetsCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


class DecisionNotFoundError(Exception):
    """Raised when a decision is not found for the given tenant."""


class InvalidOutcomesError(Exception):
    """Raised when actual_outcomes is empty or invalid."""


DECISION_STATUSES = ("committed", "executing", "completed", "rolled_back")

SELECT_BASE = """
    SELECT id, tenant_id, recommendation_id, confidence_id, authority_id,
           commitment, expected_outcomes, risk_tolerance, status, committed_at,
           executed_at, actual_outcomes
    FROM decisions
    WHERE tenant_id = :tenant_id
      AND (CAST(:status AS VARCHAR) IS NULL OR status = :status)
"""

COUNT_BASE = """
    SELECT COUNT(*) AS total
    FROM decisions
    WHERE tenant_id = :tenant_id
      AND (CAST(:status AS VARCHAR) IS NULL OR status = :status)
"""

SORT_CLAUSES = {
    "committed_at_desc": "ORDER BY committed_at DESC, id",
    "committed_at_asc": "ORDER BY committed_at ASC, id",
}

FACETS_SQL = text(
    """
    SELECT
      (SELECT COALESCE(jsonb_agg(DISTINCT status ORDER BY status), '[]')
         FROM (SELECT status FROM decisions WHERE tenant_id = :tenant_id) t) AS statuses
    """
)

SELECT_ONE = text(
    """
    SELECT id, tenant_id, recommendation_id, confidence_id, authority_id,
           commitment, expected_outcomes, risk_tolerance, status, committed_at,
           executed_at, actual_outcomes
    FROM decisions
    WHERE tenant_id = :tenant_id AND id = :id
    """
)


class DecisionReadStore:
    """Persistence gateway for tenant-scoped, paginated decision reads."""

    def __init__(self, dsn: str | None = None, engine: AsyncEngine | None = None, recommendation_store=None, confidence_store=None):
        if engine is not None:
            self._engine = engine
        else:
            self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache = FacetsCache()
        self._recommendation_store = recommendation_store
        self._confidence_store = confidence_store

    @staticmethod
    def _decision_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of an immutable decision row (the commitment
        with its falsifiable expected outcomes and the authority binding - P6:
        recorded, never executed in this MVP)."""
        expected_outcomes = row["expected_outcomes"]
        if isinstance(expected_outcomes, str):
            expected_outcomes = json.loads(expected_outcomes)
        actual_outcomes = row["actual_outcomes"]
        if isinstance(actual_outcomes, str):
            actual_outcomes = json.loads(actual_outcomes)
        payload = {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "recommendation_id": str(row["recommendation_id"]),
            "confidence_id": str(row["confidence_id"]),
            "authority_id": str(row["authority_id"]),
            "commitment": row["commitment"],
            "expected_outcomes": list(expected_outcomes or []),
            "risk_tolerance": row["risk_tolerance"],
            "status": row["status"],
            "committed_at": row["committed_at"].isoformat(),
            "executed_at": (
                row["executed_at"].isoformat() if row["executed_at"] is not None else None
            ),
            "actual_outcomes": (
                list(actual_outcomes) if actual_outcomes is not None else None
            ),
        }
        return payload

    async def list_decisions(
        self,
        *,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        sort: str = "committed_at_desc",
    ) -> dict[str, Any]:
        """Paginated, filterable read of the committed decision stream."""
        order_by = SORT_CLAUSES.get(sort, SORT_CLAUSES["committed_at_desc"])
        params = {
            "tenant_id": tenant_id,
            "limit": limit,
            "offset": offset,
            "status": status,
        }
        async with self._session_factory() as session:
            total = (
                await session.execute(text(COUNT_BASE), params)
            ).scalar_one()
            rows = await session.execute(
                text(f"{SELECT_BASE} {order_by} LIMIT :limit OFFSET :offset"),
                params,
            )
            decisions = [self._decision_payload(row) for row in rows.mappings()]
            facets = await self._facets(session, tenant_id)
        return {
            "decisions": decisions,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "facets": facets,
        }

    async def get_decision(
        self, *, tenant_id: uuid.UUID, decision_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """One decision with its desglose: the specific Recommendation being
        committed (with its leading hypothesis desglose) and the specific
        calibrated Confidence row that supports the commitment (with its own
        target desglose)."""
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_ONE,
                    {"tenant_id": tenant_id, "id": decision_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            decision = self._decision_payload(row)
            recommendation = None
            if self._recommendation_store is not None:
                recommendation = await self._recommendation_store.get_recommendation(
                    tenant_id=tenant_id, recommendation_id=row["recommendation_id"]
                )
            confidence = None
            if self._confidence_store is not None:
                confidence = await self._confidence_store.get_confidence(
                    tenant_id=tenant_id, confidence_id=row["confidence_id"]
                )
        return {
            "decision": decision,
            "recommendation": recommendation,
            "confidence": confidence,
        }

    async def _facets(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, list[str]]:
        """Distinct lifecycle statuses for the tenant (real values, not
        invented options) so the UI can offer honest filter choices."""
        cache_key = f"decisions:{tenant_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        row = (
            await session.execute(FACETS_SQL, {"tenant_id": tenant_id})
        ).mappings().one()
        facets = {
            "statuses": list(row["statuses"] or []),
        }
        self._cache.set(cache_key, facets)
        return facets

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()

    async def submit_outcomes(
        self,
        *,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        actual_outcomes: list[dict[str, Any]],
        executed_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Submit actual outcomes for a decision, populating ``actual_outcomes`` and
        ``executed_at``.

        This is the Fase 5 Outcomes integration: after a decision has been executed
        in the real world, the system records the observed outcomes and populates
        the decision row. The content trigger (sprint10) only blocks changes to
        content columns; lifecycle fields (status, executed_at, actual_outcomes)
        may be updated freely.

        Returns the updated decision payload, or raises 404 when the decision does
        not exist or 400 when the outcomes are invalid.
        """
        if not actual_outcomes:
            raise InvalidOutcomesError("actual_outcomes must be a non-empty list")

        # Check the decision exists first
        async with self._session_factory() as session:
            row = await session.execute(
                SELECT_ONE,
                {"tenant_id": str(tenant_id), "id": str(decision_id)},
            )
            decision_row = row.mappings().one_or_none()
            if decision_row is None:
                raise DecisionNotFoundError(
                    f"Decision {decision_id} not found for tenant {tenant_id}"
                )

            # Update outcomes directly
            set_parts: list[str] = []
            params: dict[str, Any] = {"id": decision_id}

            set_parts.append("actual_outcomes = :actual_outcomes")
            params["actual_outcomes"] = json.dumps(actual_outcomes, default=str)

            if executed_at is not None:
                set_parts.append("executed_at = :executed_at")
                params["executed_at"] = executed_at

            set_clause = ", ".join(set_parts)

            sql = text(
                f"""
                UPDATE decisions
                SET {set_clause}
                WHERE id = :id
                RETURNING id, tenant_id, recommendation_id, confidence_id, authority_id,
                          commitment, expected_outcomes, risk_tolerance, status, committed_at,
                          executed_at, actual_outcomes
                """
            )
            result = await session.execute(sql, params)
            await session.commit()
            row = result.mappings().one_or_none()
            if row is None:
                raise DecisionNotFoundError(
                    f"Decision {decision_id} not found"
                )

            decision = self._decision_payload(row)
            return {"decision": decision, "status": "outcomes_submitted"}