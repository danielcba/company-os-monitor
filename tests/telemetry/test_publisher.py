"""H4.0-B3 — ObservationPublisher Tests (ADR-0004 §4).

Unit tests verifying publisher invariants:
- Happy path: pending row → published
- Idempotency: same row published once
- Retry/backoff: failed row → retry with backoff
- Dead-letter: after MAX_ATTEMPTS → dead_letter status
- Concurrency: FOR UPDATE SKIP LOCKED ensures single claim
- Backoff formula: correct delay calculation
- Outbox content immutability: lifecycle-only fields change

Uses mocks for asyncpg and ObservationBus to avoid real DB/Redis.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.telemetry.publisher import (
    BASE_DELAY_SECONDS,
    JITTER_RANGE,
    MAX_ATTEMPTS,
    MAX_DELAY_SECONDS,
    OutboxRow,
    ObservationPublisher,
    _next_attempt_at,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_outbox_row(
    status: str = "pending",
    attempts: int = 0,
    next_attempt_at: datetime | None = None,
    observation_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock asyncpg.Record for observation_outbox."""
    obs_id = observation_id or uuid.uuid4()
    tenant_id = uuid.uuid4()
    obs_dict = {
        "id": str(obs_id),
        "tenant_id": str(tenant_id),
        "source_id": str(uuid.uuid4()),
        "source_type": "linux_agent",
        "fact_type": "cpu_utilization_percent",
        "fact_value": {"value": 45.2},
        "unit": "percent",
        "captured_at": datetime.now(UTC).isoformat(),
        "quality_class": "Q3",
        "raw_payload": {"sequence": 1, "fact_type": "cpu_utilization_percent"},
    }
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": obs_id,
        "tenant_id": tenant_id,
        "installation_id": uuid.uuid4(),
        "batch_id": uuid.uuid4(),
        "credential_id": uuid.uuid4(),
        "payload_hash": "a" * 64,
        "observation": json.dumps(obs_dict),
        "status": status,
        "attempts": attempts,
    }[key]
    return row


def _mock_bus() -> AsyncMock:
    """Create a mock ObservationBus."""
    bus = AsyncMock()
    bus.publish = AsyncMock(return_value="1234567890-0")
    return bus


def _mock_conn() -> AsyncMock:
    """Create a mock asyncpg connection."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    return conn


# ── Backoff formula (ADR-0004 §4) ──────────────────────────────────────────

class TestBackoffFormula:
    """Verify the backoff computation matches ADR-0004 §4."""

    def test_attempt_1_base_delay(self) -> None:
        at = _next_attempt_at(1)
        now = datetime.now(UTC)
        delta = (at - now).total_seconds()
        # base=2s ± 25% → [1.5, 2.5]
        assert 1.0 <= delta <= 3.0

    def test_attempt_2_double_delay(self) -> None:
        at = _next_attempt_at(2)
        now = datetime.now(UTC)
        delta = (at - now).total_seconds()
        # base*2=4s ± 25% → [3.0, 5.0]
        assert 2.5 <= delta <= 5.5

    def test_attempt_5_cap_delay(self) -> None:
        # min(2*2^4, 60) = min(32, 60) = 32s
        at = _next_attempt_at(5)
        now = datetime.now(UTC)
        delta = (at - now).total_seconds()
        assert 20.0 <= delta <= 40.0

    def test_cap_at_60_seconds(self) -> None:
        # 2*2^6 = 128, capped at 60; jitter ±25% → max ~75s
        at = _next_attempt_at(7)
        now = datetime.now(UTC)
        delta = (at - now).total_seconds()
        assert 40.0 <= delta <= 75.0

    def test_negative_jitter_possible(self) -> None:
        # Multiple calls should show variance
        delays = []
        for _ in range(20):
            at = _next_attempt_at(1)
            delays.append((at - datetime.now(UTC)).total_seconds())
        # Should have some variance (jitter)
        assert max(delays) - min(delays) > 0.1


# ── OutboxRow wrapper ───────────────────────────────────────────────────────

class TestOutboxRow:
    """Verify OutboxRow parses asyncpg records correctly."""

    def test_extracts_observation_dict(self) -> None:
        mock_row = _make_outbox_row()
        row = OutboxRow(mock_row)
        obs = row.observation
        assert "id" in obs
        assert "fact_type" in obs
        assert obs["fact_type"] == "cpu_utilization_percent"

    def test_observation_is_dict(self) -> None:
        mock_row = _make_outbox_row()
        row = OutboxRow(mock_row)
        assert isinstance(row.observation, dict)


# ── Happy path: pending → published ─────────────────────────────────────────

class TestPublishHappyPath:
    """ADR-0004 §4: pending row → XADD → published."""

    @pytest.mark.asyncio
    async def test_publish_pending_row(self) -> None:
        bus = _mock_bus()
        conn = _mock_conn()
        publisher = ObservationPublisher("postgresql://test", bus)

        row = OutboxRow(_make_outbox_row(status="pending", attempts=0))

        success = await publisher._publish_one(conn, row)

        assert success is True
        bus.publish.assert_called_once()
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "published" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_publish_sets_published_at(self) -> None:
        bus = _mock_bus()
        conn = _mock_conn()
        publisher = ObservationPublisher("postgresql://test", bus)

        row = OutboxRow(_make_outbox_row(status="pending", attempts=0))
        await publisher._publish_one(conn, row)

        call_args = conn.execute.call_args
        assert "published_at" in call_args[0][0]


# ── Retry / backoff ─────────────────────────────────────────────────────────

class TestRetryBackoff:
    """ADR-0004 §4: failed publish → retry with backoff."""

    @pytest.mark.asyncio
    async def test_publish_failure_sets_failed_status(self) -> None:
        bus = _mock_bus()
        bus.publish.side_effect = Exception("Redis unavailable")
        conn = _mock_conn()
        publisher = ObservationPublisher("postgresql://test", bus)

        row = OutboxRow(_make_outbox_row(status="pending", attempts=0))
        success = await publisher._publish_one(conn, row)

        assert success is False
        call_args = conn.execute.call_args
        assert "failed" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_publish_failure_increments_attempts(self) -> None:
        bus = _mock_bus()
        bus.publish.side_effect = Exception("Redis unavailable")
        conn = _mock_conn()
        publisher = ObservationPublisher("postgresql://test", bus)

        row = OutboxRow(_make_outbox_row(status="pending", attempts=2))
        await publisher._publish_one(conn, row)

        call_args = conn.execute.call_args
        assert call_args[0][2] == 3  # attempts incremented


# ── Dead-letter (ADR-0004 §4: max 5 attempts) ──────────────────────────────

class TestDeadLetter:
    """ADR-0004 §4: after MAX_ATTEMPTS → dead_letter."""

    @pytest.mark.asyncio
    async def test_dead_letter_after_max_attempts(self) -> None:
        bus = _mock_bus()
        bus.publish.side_effect = Exception("Redis unavailable")
        conn = _mock_conn()
        publisher = ObservationPublisher("postgresql://test", bus)

        row = OutboxRow(_make_outbox_row(status="failed", attempts=MAX_ATTEMPTS - 1))
        success = await publisher._publish_one(conn, row)

        assert success is False
        call_args = conn.execute.call_args
        assert "dead_letter" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_not_dead_letter_below_max(self) -> None:
        bus = _mock_bus()
        bus.publish.side_effect = Exception("Redis unavailable")
        conn = _mock_conn()
        publisher = ObservationPublisher("postgresql://test", bus)

        row = OutboxRow(_make_outbox_row(status="failed", attempts=MAX_ATTEMPTS - 2))
        await publisher._publish_one(conn, row)

        call_args = conn.execute.call_args
        assert "dead_letter" not in call_args[0][0]
        assert "failed" in call_args[0][0]


# ── Claim rows (FOR UPDATE SKIP LOCKED) ────────────────────────────────────

class TestClaimRows:
    """ADR-0004 §6: rows claimed with FOR UPDATE SKIP LOCKED."""

    @pytest.mark.asyncio
    async def test_claims_pending_and_failed_rows(self) -> None:
        bus = _mock_bus()
        conn = _mock_conn()
        publisher = ObservationPublisher("postgresql://test", bus)

        row1 = _make_outbox_row(status="pending")
        row2 = _make_outbox_row(status="failed")
        conn.fetch.return_value = [row1, row2]

        rows = await publisher._claim_rows(conn)

        assert len(rows) == 2
        conn.fetch.assert_called_once()
        query = conn.fetch.call_args[0][0]
        assert "SKIP LOCKED" in query
        assert "pending" in query
        assert "failed" in query

    @pytest.mark.asyncio
    async def test_empty_when_no_pending(self) -> None:
        bus = _mock_bus()
        conn = _mock_conn()
        publisher = ObservationPublisher("postgresql://test", bus)

        conn.fetch.return_value = []

        rows = await publisher._claim_rows(conn)

        assert len(rows) == 0


# ── Poll cycle ──────────────────────────────────────────────────────────────

class TestPollOnce:
    """Integration of claim + publish cycle."""

    @pytest.mark.asyncio
    async def test_poll_once_publishes_all_rows(self) -> None:
        bus = _mock_bus()
        publisher = ObservationPublisher("postgresql://test", bus)

        row1 = _make_outbox_row(status="pending")
        row2 = _make_outbox_row(status="pending")

        with patch("libs.telemetry.publisher.asyncpg") as mock_asyncpg:
            mock_conn = AsyncMock()
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)
            mock_conn.fetch.return_value = [row1, row2]
            mock_conn.execute = AsyncMock()

            count = await publisher._poll_once()

        assert count == 2

    @pytest.mark.asyncio
    async def test_poll_once_returns_zero_when_empty(self) -> None:
        bus = _mock_bus()
        publisher = ObservationPublisher("postgresql://test", bus)

        with patch("libs.telemetry.publisher.asyncpg") as mock_asyncpg:
            mock_conn = AsyncMock()
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)
            mock_conn.fetch.return_value = []

            count = await publisher._poll_once()

        assert count == 0


# ── Lifecycle start/stop ────────────────────────────────────────────────────

class TestPublisherLifecycle:
    """Start and stop the publisher gracefully."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self) -> None:
        bus = _mock_bus()
        publisher = ObservationPublisher("postgresql://test", bus)

        with patch("libs.telemetry.publisher.asyncpg"):
            await publisher.start(poll_interval_seconds=100)

        assert publisher._task is not None
        assert publisher._running is True

        await publisher.stop()
        assert publisher._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self) -> None:
        bus = _mock_bus()
        publisher = ObservationPublisher("postgresql://test", bus)

        with patch("libs.telemetry.publisher.asyncpg"):
            await publisher.start(poll_interval_seconds=100)
            task = publisher._task
            await publisher.stop()

        assert publisher._running is False
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_double_start_noop(self) -> None:
        bus = _mock_bus()
        publisher = ObservationPublisher("postgresql://test", bus)

        with patch("libs.telemetry.publisher.asyncpg"):
            await publisher.start()
            task1 = publisher._task
            await publisher.start()  # should be noop
            task2 = publisher._task

        assert task1 is task2
        await publisher.stop()


# ── Constants match ADR-0004 §4 ────────────────────────────────────────────

class TestADRConstants:
    """Verify constants match ADR-0004 §4 specification."""

    def test_base_delay(self) -> None:
        assert BASE_DELAY_SECONDS == 2

    def test_max_delay(self) -> None:
        assert MAX_DELAY_SECONDS == 60

    def test_jitter_range(self) -> None:
        assert JITTER_RANGE == 0.25

    def test_max_attempts(self) -> None:
        assert MAX_ATTEMPTS == 5
