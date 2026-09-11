"""Observation Publisher — outbox → Redis Streams (ADR-0004 §4).

Polls ``observation_outbox`` for pending/failed rows, claims them via
``SELECT ... FOR UPDATE SKIP LOCKED``, publishes each Observation to
Redis Streams via ``ObservationBus``, and updates lifecycle status.

Delivery semantics: at-least-once (ADR-0004 §5).  Deterministic Observation
IDs guarantee idempotent downstream consumption by the Collector.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from libs.cognitive_core.observation_bus import Observation, ObservationBus

logger = logging.getLogger(__name__)

# ── ADR-0004 §4 constants ──────────────────────────────────────────────────

BASE_DELAY_SECONDS = 2
MAX_DELAY_SECONDS = 60
JITTER_RANGE = 0.25  # ±25%
MAX_ATTEMPTS = 5


def _next_attempt_at(attempts: int) -> datetime:
    """Compute next_attempt_at per ADR-0004 §4 backoff formula."""
    delay = min(BASE_DELAY_SECONDS * (2 ** (attempts - 1)), MAX_DELAY_SECONDS)
    jitter = delay * random.uniform(-JITTER_RANGE, JITTER_RANGE)
    return datetime.now(UTC) + timedelta(seconds=delay + jitter)


# ── Observation row representation ──────────────────────────────────────────

class OutboxRow:
    """Typed wrapper for a single observation_outbox row."""

    def __init__(self, row: asyncpg.Record) -> None:
        self.id: uuid.UUID = row["id"]
        self.tenant_id: uuid.UUID = row["tenant_id"]
        self.installation_id: uuid.UUID = row["installation_id"]
        self.batch_id: uuid.UUID = row["batch_id"]
        self.credential_id: uuid.UUID = row["credential_id"]
        self.payload_hash: str = row["payload_hash"]
        self.observation_raw: dict[str, Any] = row["observation"]
        self.status: str = row["status"]
        self.attempts: int = row["attempts"]

    @property
    def observation(self) -> dict[str, Any]:
        raw = self.observation_raw
        return json.loads(raw) if isinstance(raw, str) else raw


# ── Publisher ────────────────────────────────────────────────────────────────

class ObservationPublisher:
    """Background worker: outbox → Redis Streams (ADR-0004 §4).

    Usage::

        publisher = ObservationPublisher(dsn, redis_client)
        await publisher.start()   # polls in background
        ...
        await publisher.stop()    # graceful shutdown
    """

    def __init__(self, dsn: str, bus: ObservationBus) -> None:
        self._dsn = dsn
        self._bus = bus
        self._task: asyncio.Task[None] | None = None
        self._running = False

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def start(self, poll_interval_seconds: float = 2.0) -> None:
        """Start the background polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(poll_interval_seconds))
        logger.info("ObservationPublisher started (interval=%.1fs)", poll_interval_seconds)

    async def stop(self) -> None:
        """Gracefully stop the publisher."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("ObservationPublisher stopped")

    # ── Poll loop ────────────────────────────────────────────────────────

    async def _poll_loop(self, interval: float) -> None:
        """Main loop: poll outbox, claim and publish rows."""
        while self._running:
            try:
                published = await self._poll_once()
                if published == 0:
                    await asyncio.sleep(interval)
                else:
                    # Immediately re-poll when work was done
                    pass
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001 - publisher must not crash on any error
                logger.exception("ObservationPublisher poll cycle error")
                await asyncio.sleep(interval)

    async def _poll_once(self) -> int:
        """Claim and publish one batch of pending rows. Returns count published."""
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await self._claim_rows(conn)
            if not rows:
                return 0
            published = 0
            for row in rows:
                success = await self._publish_one(conn, row)
                if success:
                    published += 1
            return published
        finally:
            await conn.close()

    # ── Claim rows (ADR-0004 §6: FOR UPDATE SKIP LOCKED) ────────────────

    async def _claim_rows(
        self, conn: asyncpg.Connection, batch_size: int = 10,
    ) -> list[OutboxRow]:
        """Claim pending/failed rows with row-level locking."""
        rows = await conn.fetch(
            "SELECT id, tenant_id, installation_id, batch_id, credential_id, "
            " payload_hash, observation, status, attempts "
            "FROM observation_outbox "
            "WHERE (status = 'pending' "
            "       OR (status = 'failed' AND next_attempt_at <= now())) "
            "ORDER BY next_attempt_at "
            "LIMIT $1 "
            "FOR UPDATE SKIP LOCKED",
            batch_size,
        )
        return [OutboxRow(r) for r in rows]

    # ── Publish one row ──────────────────────────────────────────────────

    async def _publish_one(self, conn: asyncpg.Connection, row: OutboxRow) -> bool:
        """Publish a single outbox row to Redis. Returns True on success."""
        try:
            obs_dict = row.observation
            obs = Observation(
                id=uuid.UUID(obs_dict["id"]),
                tenant_id=uuid.UUID(obs_dict["tenant_id"]),
                source_id=uuid.UUID(obs_dict["source_id"]),
                source_type=obs_dict.get("source_type", "unknown"),
                fact_type=obs_dict["fact_type"],
                fact_value=obs_dict.get("fact_value", {}),
                unit=obs_dict.get("unit", ""),
                captured_at=datetime.fromisoformat(obs_dict["captured_at"]),
                quality_class=obs_dict.get("quality_class", "Q3"),
                raw_payload=obs_dict.get("raw_payload", {}),
            )
            await self._bus.publish(obs)
        except Exception:  # noqa: BLE001 - publisher must handle any Redis/DB error
            new_attempts = row.attempts + 1
            if new_attempts >= MAX_ATTEMPTS:
                await conn.execute(
                    "UPDATE observation_outbox "
                    "SET status = 'dead_letter', attempts = $2, "
                    "    last_error = $3, next_attempt_at = $4 "
                    "WHERE id = $1",
                    row.id, new_attempts,
                    "max attempts exceeded",
                    datetime.now(UTC),
                )
                logger.warning(
                    "Observation %s dead-lettered after %d attempts", row.id, new_attempts,
                )
            else:
                next_at = _next_attempt_at(new_attempts)
                await conn.execute(
                    "UPDATE observation_outbox "
                    "SET status = 'failed', attempts = $2, "
                    "    last_error = $3, next_attempt_at = $4 "
                    "WHERE id = $1",
                    row.id, new_attempts,
                    "publish failed",
                    next_at,
                )
                logger.debug(
                    "Observation %s failed (attempt %d), retry at %s",
                    row.id, new_attempts, next_at,
                )
            return False
        else:
            await conn.execute(
                "UPDATE observation_outbox "
                "SET status = 'published', published_at = now(), attempts = attempts + 1 "
                "WHERE id = $1",
                row.id,
            )
            logger.debug("Published observation %s", row.id)
            return True
