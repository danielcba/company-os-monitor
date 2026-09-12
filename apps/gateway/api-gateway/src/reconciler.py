"""Heartbeat Reconciler — ADR-0006 §9.

Transitions stale RUNNING agent_instances to STOPPED when their
last_heartbeat_at exceeds the configured timeout. Runs as a background
asyncio task, started/stopped with the gateway lifecycle.

Concurrency safety:
- Uses a single UPDATE ... WHERE statement per cycle (atomic at row level).
- At-most-one RUNNING per installation enforced by partial UNIQUE index
  (uq_agent_instances_active) — no reconciler logic can violate this.
- Idempotent: STOPPED instances are never touched; already-stale instances
  that become STOPPED between cycles are harmless.
"""
import asyncio
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 120
DEFAULT_RECONCILE_INTERVAL_SECONDS = 30


class HeartbeatReconciler:
    """Background task that stops stale RUNNING agent instances."""

    def __init__(
        self,
        dsn: str,
        *,
        heartbeat_timeout_seconds: int = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
        reconcile_interval_seconds: int = DEFAULT_RECONCILE_INTERVAL_SECONDS,
    ) -> None:
        self._dsn = dsn
        self._timeout = heartbeat_timeout_seconds
        self._interval = reconcile_interval_seconds
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the reconciler background loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="heartbeat-reconciler")
        logger.info(
            "Heartbeat reconciler started (timeout=%ds, interval=%ds)",
            self._timeout,
            self._interval,
        )

    async def stop(self) -> None:
        """Stop the reconciler gracefully."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Heartbeat reconciler stopped")

    async def _run(self) -> None:
        """Main reconciliation loop."""
        while True:
            try:
                await self._reconcile_cycle()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Heartbeat reconcile cycle failed")
            await asyncio.sleep(self._interval)

    async def _reconcile_cycle(self) -> int:
        """Transition stale RUNNING instances to STOPPED.

        Returns the number of instances transitioned.
        """
        import asyncpg

        cutoff = datetime.now(UTC).timestamp() - self._timeout
        cutoff_dt = datetime.fromtimestamp(cutoff, tz=UTC)

        try:
            conn = await asyncpg.connect(self._dsn)
            try:
                result = await conn.execute(
                    "UPDATE agent_instances SET status = 'STOPPED', stopped_at = now() "
                    "WHERE status = 'RUNNING' AND last_heartbeat_at < $1",
                    cutoff_dt,
                )
                # result like "UPDATE 3"
                count = int(result.split()[-1]) if result and result.split()[-1].isdigit() else 0
                if count > 0:
                    logger.info("Heartbeat reconciler: stopped %d stale instance(s)", count)
                return count
            finally:
                await conn.close()
        except Exception:
            logger.exception("Heartbeat reconciler DB error")
            return 0
