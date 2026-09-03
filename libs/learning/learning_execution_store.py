"""Learning Execution Store (H3 — advisory lock + transaction protocol).

Implements the Phase 2 transaction for learning execution:
- Transaction-scoped PostgreSQL advisory lock per decision
- Idempotent execution creation via UNIQUE partial index
- Single-transaction persistence of all signals
- Heartbeat updates (separate transaction)

The advisory lock key is: hashtext("{tenant_id}:{decision_id}")
Lock is transaction-scoped (pg_advisory_xact_lock) — auto-released on
COMMIT/ROLLBACK. This matches the existing pattern in ContextStore.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from libs.learning.learning_execution import (
    LearningExecution,
    is_stale,
)
from libs.learning.outcome_revision import OutcomeRevision

# ── SQL statements ──────────────────────────────────────────────────────────

_INSERT_OUTCOME_REVISION = text(
    """
    INSERT INTO outcome_revisions (tenant_id, decision_id, actual_outcomes, executed_at)
    VALUES (:tenant_id, :decision_id, CAST(:actual_outcomes AS jsonb), :executed_at)
    RETURNING id, tenant_id, decision_id, actual_outcomes, executed_at, created_at
    """
)

_INSERT_EXECUTION = text(
    """
    INSERT INTO learning_executions
        (tenant_id, decision_id, outcome_revision_id, status, attempt_number,
         parent_execution_id, heartbeat_at)
    VALUES
        (:tenant_id, :decision_id, :outcome_revision_id, :status, :attempt_number,
         :parent_execution_id, now())
    RETURNING id, tenant_id, decision_id, outcome_revision_id, status,
              attempt_number, parent_execution_id, started_at, completed_at,
              heartbeat_at, signal_count, failure_reason, created_at
    """
)

_FIND_ACTIVE_EXECUTION = text(
    """
    SELECT id, tenant_id, decision_id, outcome_revision_id, status,
           attempt_number, parent_execution_id, started_at, completed_at,
           heartbeat_at, signal_count, failure_reason, created_at
    FROM learning_executions
    WHERE outcome_revision_id = :outcome_revision_id
      AND status IN ('pending', 'running')
    ORDER BY attempt_number DESC
    LIMIT 1
    """
)

_FIND_LATEST_EXECUTION = text(
    """
    SELECT id, tenant_id, decision_id, outcome_revision_id, status,
           attempt_number, parent_execution_id, started_at, completed_at,
           heartbeat_at, signal_count, failure_reason, created_at
    FROM learning_executions
    WHERE outcome_revision_id = :outcome_revision_id
    ORDER BY attempt_number DESC
    LIMIT 1
    """
)

_UPDATE_EXECUTION_STATUS = text(
    """
    UPDATE learning_executions
    SET status = :status,
        started_at = COALESCE(:started_at, started_at),
        completed_at = COALESCE(:completed_at, completed_at),
        heartbeat_at = COALESCE(:heartbeat_at, heartbeat_at),
        signal_count = COALESCE(:signal_count, signal_count),
        failure_reason = COALESCE(:failure_reason, failure_reason)
    WHERE id = :id
    RETURNING id, tenant_id, decision_id, outcome_revision_id, status,
              attempt_number, parent_execution_id, started_at, completed_at,
              heartbeat_at, signal_count, failure_reason, created_at
    """
)

_UPDATE_HEARTBEAT = text(
    """
    UPDATE learning_executions
    SET heartbeat_at = now()
    WHERE id = :id AND status = 'running'
    """
)

_FIND_STALE_EXECUTIONS = text(
    """
    SELECT id, tenant_id, decision_id, outcome_revision_id, status,
           attempt_number, parent_execution_id, started_at, completed_at,
           heartbeat_at, signal_count, failure_reason, created_at
    FROM learning_executions
    WHERE status = 'running'
      AND heartbeat_at < now() - (:stale_threshold || ' seconds')::interval
    """
)

_FIND_ORPHANED_REVISIONS = text(
    """
    SELECT id, tenant_id, decision_id, actual_outcomes, executed_at, created_at
    FROM outcome_revisions
    WHERE NOT EXISTS (
        SELECT 1 FROM learning_executions
        WHERE learning_executions.outcome_revision_id = outcome_revisions.id
    )
    """
)

_ADVISORY_LOCK_SQL = text(
    "SELECT pg_advisory_xact_lock(hashtext(:lock_key))"
)


def _lock_key(tenant_id: uuid.UUID, decision_id: uuid.UUID) -> str:
    """Derive the advisory lock key for a decision (same as ContextStore pattern)."""
    return f"{tenant_id}:{decision_id}"


def _row_to_execution(row) -> LearningExecution:
    return LearningExecution(
        id=row["id"],
        tenant_id=row["tenant_id"],
        decision_id=row["decision_id"],
        outcome_revision_id=row["outcome_revision_id"],
        status=row["status"],
        attempt_number=row["attempt_number"],
        parent_execution_id=row["parent_execution_id"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        heartbeat_at=row["heartbeat_at"],
        signal_count=row["signal_count"] or 0,
        failure_reason=row["failure_reason"],
        created_at=row["created_at"],
    )


def _row_to_revision(row) -> OutcomeRevision:
    actual = row["actual_outcomes"]
    if isinstance(actual, str):
        actual = json.loads(actual)
    return OutcomeRevision(
        id=row["id"],
        tenant_id=row["tenant_id"],
        decision_id=row["decision_id"],
        actual_outcomes=actual,
        executed_at=row["executed_at"],
        created_at=row["created_at"],
    )


class LearningExecutionStore:
    """Durable execution store with advisory lock and transaction protocol.

    Implements the approved H3 Phase 1/Phase 2 transaction model:
    - Phase 1 (lock-free): INSERT outcome_revision + UPDATE decisions
    - Phase 2 (advisory-locked): INSERT execution + compute + INSERT memory
    """

    def __init__(
        self,
        dsn: str | None = None,
        engine: AsyncEngine | None = None,
    ) -> None:
        if engine is not None:
            self._engine = engine
            self._owns_engine = False
        elif dsn:
            self._engine = create_async_engine(dsn)
            self._owns_engine = True
        else:
            raise ValueError("LearningExecutionStore requires dsn or engine")  # noqa: TRY003
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    # ── Phase 1: Outcome Revision (lock-free, append-only) ──────────────

    async def create_outcome_revision(
        self,
        *,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        actual_outcomes: list[dict[str, Any]],
        executed_at: datetime | None = None,
    ) -> OutcomeRevision:
        """Phase 1: Create an outcome revision (lock-free, append-only, P6)."""
        async with self._session_factory() as session:
            result = await session.execute(
                _INSERT_OUTCOME_REVISION,
                {
                    "tenant_id": tenant_id,
                    "decision_id": decision_id,
                    "actual_outcomes": json.dumps(actual_outcomes, default=str),
                    "executed_at": executed_at,
                },
            )
            row = result.mappings().one()
            await session.commit()
            return _row_to_revision(row)

    async def submit_outcomes_with_revision(
        self,
        *,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        actual_outcomes: list[dict[str, Any]],
        executed_at: datetime | None = None,
    ) -> OutcomeRevision:
        """Atomic Phase 1: INSERT outcome_revision + UPDATE decisions (F-02).

        Both operations execute in a single transaction. If either fails,
        the entire Phase 1 rolls back — no partial state.
        """
        async with self._session_factory() as session, session.begin():
            # 1. INSERT outcome revision (append-only, P6)
            result = await session.execute(
                _INSERT_OUTCOME_REVISION,
                {
                    "tenant_id": tenant_id,
                    "decision_id": decision_id,
                    "actual_outcomes": json.dumps(actual_outcomes, default=str),
                    "executed_at": executed_at,
                },
            )
            revision_row = result.mappings().one()

            # 2. UPDATE decisions (lifecycle fields only — content is immutable)
            set_parts: list[str] = []
            params: dict[str, Any] = {"id": decision_id, "tenant_id": tenant_id}
            set_parts.append("actual_outcomes = :actual_outcomes")
            params["actual_outcomes"] = json.dumps(actual_outcomes, default=str)
            if executed_at is not None:
                set_parts.append("executed_at = :executed_at")
                params["executed_at"] = executed_at

            update_result = await session.execute(
                text(
                    f"UPDATE decisions SET {', '.join(set_parts)} "
                    "WHERE id = :id AND tenant_id = :tenant_id "
                    "RETURNING id"
                ),
                params,
            )
            if update_result.mappings().one_or_none() is None:
                raise ValueError(  # noqa: TRY003
                    f"Decision {decision_id} not found for tenant {tenant_id}"
                )

            # Transaction commits here (session.begin() context manager exits)
            return _row_to_revision(revision_row)

    # ── Phase 2: Learning Execution (advisory-locked) ───────────────────

    async def begin_execution(
        self,
        *,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        outcome_revision_id: uuid.UUID,
    ) -> LearningExecution | None:
        """Phase 2 entry: acquire advisory lock and create/claim execution.

        Returns the execution in 'running' status, or None if the execution
        is already completed (idempotent skip).

        Implements the full state machine transition inside the advisory lock:
        - NULL → INSERT pending → UPDATE running
        - pending → UPDATE running
        - running (stale) → INSERT new execution
        - completed → SKIP (return None)
        """
        async with self._session_factory() as session, session.begin():
            # Advisory lock: serialize on (tenant_id, decision_id)
            await session.execute(
                _ADVISORY_LOCK_SQL,
                {"lock_key": _lock_key(tenant_id, decision_id)},
            )

            # Check for existing active execution
            result = await session.execute(
                _FIND_ACTIVE_EXECUTION,
                {"outcome_revision_id": outcome_revision_id},
            )
            existing = result.mappings().one_or_none()

            if existing is not None:
                status = existing["status"]
                if status == "completed":
                    # Already completed — idempotent skip
                    return None
                if status == "running":
                    # Already running — check heartbeat staleness
                    ex = _row_to_execution(existing)
                    if not is_stale(ex):
                        return None  # Still active, skip
                    # Stale — mark old execution and create new one
                    await session.execute(
                        _UPDATE_EXECUTION_STATUS,
                        {
                            "id": existing["id"],
                            "status": "stale",
                            "completed_at": datetime.now(UTC),
                        },
                    )
                    # Fall through to create new execution
                    attempt = existing["attempt_number"] + 1
                    parent_id = existing["id"]
                elif status == "pending":
                    # Pending — transition to running
                    await session.execute(
                        _UPDATE_EXECUTION_STATUS,
                        {
                            "id": existing["id"],
                            "status": "running",
                            "started_at": datetime.now(UTC),
                            "heartbeat_at": datetime.now(UTC),
                        },
                    )
                    return _row_to_execution(
                        {**dict(existing), "status": "running",
                         "started_at": datetime.now(UTC),
                         "heartbeat_at": datetime.now(UTC)}
                    )
                else:
                    return None
            else:
                attempt = 1
                parent_id = None

            # Create new execution
            result = await session.execute(
                _INSERT_EXECUTION,
                {
                    "tenant_id": tenant_id,
                    "decision_id": decision_id,
                    "outcome_revision_id": outcome_revision_id,
                    "status": "running",
                    "attempt_number": attempt,
                    "parent_execution_id": parent_id,
                },
            )
            row = result.mappings().one()
            return _row_to_execution(row)

    async def complete_execution(
        self,
        *,
        execution_id: uuid.UUID,
        signal_count: int,
    ) -> LearningExecution | None:
        """Mark execution as completed (within the same advisory-locked transaction)."""
        async with self._session_factory() as session:
            result = await session.execute(
                _UPDATE_EXECUTION_STATUS,
                {
                    "id": execution_id,
                    "status": "completed",
                    "completed_at": datetime.now(UTC),
                    "signal_count": signal_count,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return _row_to_execution(row) if row is not None else None

    async def fail_execution(
        self,
        *,
        execution_id: uuid.UUID,
        failure_reason: str,
    ) -> LearningExecution | None:
        """Mark execution as failed (within the same advisory-locked transaction)."""
        async with self._session_factory() as session:
            result = await session.execute(
                _UPDATE_EXECUTION_STATUS,
                {
                    "id": execution_id,
                    "status": "failed",
                    "completed_at": datetime.now(UTC),
                    "failure_reason": failure_reason,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return _row_to_execution(row) if row is not None else None

    # ── Phase 2: Single-transaction protocol (F-01 remediation) ─────────

    async def begin_phase2(
        self,
        *,
        tenant_id: uuid.UUID,
        decision_id: uuid.UUID,
        outcome_revision_id: uuid.UUID,
    ) -> tuple[LearningExecution, AsyncSession]:
        """Acquire advisory lock and create/claim execution, returning the open session.

        The caller MUST eventually commit or rollback the returned session.
        The advisory lock is held for the lifetime of the transaction.

        Returns (execution, session) where session is inside a transaction
        with the advisory lock held. Returns (None, session) if already
        completed (idempotent skip) — caller must rollback the session.
        """
        session = await self._session_factory().__aenter__()
        # Use begin() to start a transaction; advisory lock is transaction-scoped
        await session.begin()
        await session.execute(
            _ADVISORY_LOCK_SQL,
            {"lock_key": _lock_key(tenant_id, decision_id)},
        )

        # Check for existing active execution
        result = await session.execute(
            _FIND_ACTIVE_EXECUTION,
            {"outcome_revision_id": outcome_revision_id},
        )
        existing = result.mappings().one_or_none()

        if existing is not None:
            status = existing["status"]
            if status == "completed":
                return (None, session)  # type: ignore[return-value]
            if status == "running":
                ex = _row_to_execution(existing)
                if not is_stale(ex):
                    return (None, session)  # type: ignore[return-value]
                # Stale — mark old execution and create new one
                await session.execute(
                    _UPDATE_EXECUTION_STATUS,
                    {
                        "id": existing["id"],
                        "status": "stale",
                        "completed_at": datetime.now(UTC),
                    },
                )
                attempt = existing["attempt_number"] + 1
                parent_id = existing["id"]
            elif status == "pending":
                await session.execute(
                    _UPDATE_EXECUTION_STATUS,
                    {
                        "id": existing["id"],
                        "status": "running",
                        "started_at": datetime.now(UTC),
                        "heartbeat_at": datetime.now(UTC),
                    },
                )
                return (
                    _row_to_execution(
                        {**dict(existing), "status": "running",
                         "started_at": datetime.now(UTC),
                         "heartbeat_at": datetime.now(UTC)}
                    ),
                    session,
                )
            else:
                return (None, session)  # type: ignore[return-value]
        else:
            attempt = 1
            parent_id = None

        # Create new execution
        result = await session.execute(
            _INSERT_EXECUTION,
            {
                "tenant_id": tenant_id,
                "decision_id": decision_id,
                "outcome_revision_id": outcome_revision_id,
                "status": "running",
                "attempt_number": attempt,
                "parent_execution_id": parent_id,
            },
        )
        row = result.mappings().one()
        return (_row_to_execution(row), session)

    async def complete_execution_in_session(
        self,
        *,
        session: AsyncSession,
        execution_id: uuid.UUID,
        signal_count: int,
    ) -> LearningExecution | None:
        """Mark execution as completed within the caller's transaction (F-01)."""
        result = await session.execute(
            text(
                "UPDATE learning_executions "
                "SET status = :status, completed_at = :completed_at, signal_count = :signal_count "
                "WHERE id = :id "
                "RETURNING id, tenant_id, decision_id, outcome_revision_id, status, "
                "attempt_number, parent_execution_id, started_at, completed_at, "
                "heartbeat_at, signal_count, failure_reason, created_at"
            ),
            {
                "id": execution_id,
                "status": "completed",
                "completed_at": datetime.now(UTC),
                "signal_count": signal_count,
            },
        )
        row = result.mappings().one_or_none()
        return _row_to_execution(row) if row is not None else None

    async def fail_execution_in_session(
        self,
        *,
        session: AsyncSession,
        execution_id: uuid.UUID,
        failure_reason: str,
    ) -> LearningExecution | None:
        """Mark execution as failed within the caller's transaction (F-01)."""
        result = await session.execute(
            text(
                "UPDATE learning_executions "
                "SET status = :status, completed_at = :completed_at, "
                "failure_reason = :failure_reason "
                "WHERE id = :id "
                "RETURNING id, tenant_id, decision_id, outcome_revision_id, status, "
                "attempt_number, parent_execution_id, started_at, completed_at, "
                "heartbeat_at, signal_count, failure_reason, created_at"
            ),
            {
                "id": execution_id,
                "status": "failed",
                "completed_at": datetime.now(UTC),
                "failure_reason": failure_reason,
            },
        )
        row = result.mappings().one_or_none()
        return _row_to_execution(row) if row is not None else None

    # ── Heartbeat (separate transaction) ────────────────────────────────

    async def update_heartbeat(self, *, execution_id: uuid.UUID) -> None:
        """Update heartbeat timestamp (separate transaction, no lock needed)."""
        async with self._session_factory() as session:
            await session.execute(
                _UPDATE_HEARTBEAT,
                {"id": execution_id},
            )
            await session.commit()

    # ── Read operations ─────────────────────────────────────────────────

    async def get_execution(
        self, *, execution_id: uuid.UUID
    ) -> LearningExecution | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, tenant_id, decision_id, outcome_revision_id, "
                    "status, attempt_number, parent_execution_id, started_at, "
                    "completed_at, heartbeat_at, signal_count, failure_reason, "
                    "created_at FROM learning_executions WHERE id = :id"
                ),
                {"id": execution_id},
            )
            row = result.mappings().one_or_none()
            return _row_to_execution(row) if row is not None else None

    async def get_latest_execution_for_revision(
        self, *, outcome_revision_id: uuid.UUID
    ) -> LearningExecution | None:
        async with self._session_factory() as session:
            result = await session.execute(
                _FIND_LATEST_EXECUTION,
                {"outcome_revision_id": outcome_revision_id},
            )
            row = result.mappings().one_or_none()
            return _row_to_execution(row) if row is not None else None

    # ── Reconciliation ──────────────────────────────────────────────────

    async def find_stale_executions(
        self, *, stale_threshold_seconds: int = 300
    ) -> list[LearningExecution]:
        """Find executions that are running but have expired heartbeats."""
        async with self._session_factory() as session:
            result = await session.execute(
                _FIND_STALE_EXECUTIONS,
                {"stale_threshold": str(stale_threshold_seconds)},
            )
            return [_row_to_execution(r) for r in result.mappings().all()]

    async def find_orphaned_revisions(self) -> list[OutcomeRevision]:
        """F-1: Find outcome_revisions without corresponding learning_executions."""
        async with self._session_factory() as session:
            result = await session.execute(_FIND_ORPHANED_REVISIONS)
            return [_row_to_revision(r) for r in result.mappings().all()]

    async def reconcile_stale_execution(
        self,
        *,
        stale_execution: LearningExecution,
    ) -> LearningExecution | None:
        """Reconcile a stale execution: acquire lock, re-read state, retry if safe.

        The reconciliation protocol (H3.3):
        1. Acquire the same advisory lock as normal execution
        2. Re-read execution state (may have changed since detection)
        3. Re-read heartbeat (may have been updated)
        4. Revalidate retry eligibility
        5. Transition safely
        6. Create new execution for retry

        Returns the new execution in 'running' status, or None if the
        execution is no longer eligible for retry (already completed,
        already has a newer execution, etc.).
        """
        async with self._session_factory() as session, session.begin():
            # 1. Acquire advisory lock (same key as normal execution)
            await session.execute(
                _ADVISORY_LOCK_SQL,
                {"lock_key": _lock_key(stale_execution.tenant_id, stale_execution.decision_id)},
            )

            # 2. Re-read execution state
            result = await session.execute(
                text(
                    "SELECT id, tenant_id, decision_id, outcome_revision_id, "
                    "status, attempt_number, parent_execution_id, started_at, "
                    "completed_at, heartbeat_at, signal_count, failure_reason, "
                    "created_at FROM learning_executions WHERE id = :id"
                ),
                {"id": stale_execution.id},
            )
            current = result.mappings().one_or_none()
            if current is None:
                return None

            current_ex = _row_to_execution(current)

            # 3. Re-read heartbeat and revalidate staleness
            if not is_stale(current_ex):
                # Worker resumed — no longer stale, skip
                return None

            # 4. Check if already has a newer execution
            result = await session.execute(
                _FIND_ACTIVE_EXECUTION,
                {"outcome_revision_id": current_ex.outcome_revision_id},
            )
            active = result.mappings().one_or_none()
            if active is not None and active["id"] != current_ex.id:
                # Another execution already active for this revision
                return None

            # 5. Transition to stale
            await session.execute(
                _UPDATE_EXECUTION_STATUS,
                {
                    "id": current_ex.id,
                    "status": "stale",
                    "completed_at": datetime.now(UTC),
                },
            )

            # 6. Create new execution for retry
            result = await session.execute(
                _INSERT_EXECUTION,
                {
                    "tenant_id": current_ex.tenant_id,
                    "decision_id": current_ex.decision_id,
                    "outcome_revision_id": current_ex.outcome_revision_id,
                    "status": "running",
                    "attempt_number": current_ex.attempt_number + 1,
                    "parent_execution_id": current_ex.id,
                },
            )
            row = result.mappings().one()
            return _row_to_execution(row)

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def verify_connection(self) -> None:
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        if self._owns_engine:
            await self._engine.dispose()
