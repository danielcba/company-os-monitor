"""Unit tests for the Learning Memory ledger (P7 persistence) — pure logic.

No IO: exercises the deterministic signal hash, target-type guard, payload
shape, and the idempotent-persist contract via a fake store that implements
the MemoryStoreProtocol.
"""
import uuid

from libs.memory.memory_ledger import (
    TARGET_TYPES,
    LearningMemoryRecord,
    MemoryStoreProtocol,
    PersistLearningMemoryInput,
    compute_signal_hash,
)


def _record(target_type="pattern", target_id=None, signal=None) -> LearningMemoryRecord:
    return LearningMemoryRecord(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(int=1),
        target_type=target_type,
        target_id=target_id or uuid.uuid4(),
        signal=signal or {"action": "keep"},
        provenance={"decisions": 1},
        signal_hash="x" * 64,
        created_at=__import__("datetime").datetime(2026, 1, 1),
    )


def test_target_types_are_canonical():
    assert {"pattern", "context", "insight", "decision"} == TARGET_TYPES


def test_signal_hash_is_deterministic_and_order_independent():
    a = compute_signal_hash({"b": 1, "a": 2})
    b = compute_signal_hash({"a": 2, "b": 1})
    assert a == b
    assert len(a) == 64  # noqa: PLR2004


def test_signal_hash_differs_on_content_change():
    assert compute_signal_hash({"a": 1}) != compute_signal_hash({"a": 2})


def test_record_payload_serializes_uuids_and_dates():
    rec = _record()
    p = rec.to_payload()
    assert isinstance(p["id"], str)
    assert isinstance(p["target_id"], str)
    assert p["created_at"].startswith("2026-01-01")
    assert p["signal"] == {"action": "keep"}


class _FakeMemoryStore:
    """In-memory implementation of MemoryStoreProtocol (no PG)."""

    def __init__(self):
        self._rows = {}
        self.persisted = []

    async def persist(self, *, record: PersistLearningMemoryInput) -> LearningMemoryRecord:
        h = compute_signal_hash(record.signal)
        key = (record.tenant_id, record.target_type, record.target_id, h)
        if key in self._rows:
            return self._rows[key]  # idempotent no-op
        rec = _record(
            target_type=record.target_type,
            target_id=record.target_id,
            signal=record.signal,
        )
        rec.tenant_id = record.tenant_id
        rec.signal_hash = h
        self._rows[key] = rec
        self.persisted.append(rec)
        return rec

    async def list(self, *, tenant_id, target_type=None, target_id=None):
        out = []
        for rec in self._rows.values():
            if rec.tenant_id != tenant_id:
                continue
            if target_type and rec.target_type != target_type:
                continue
            if target_id and rec.target_id != target_id:
                continue
            out.append(rec)
        return out

    async def get_latest(self, *, tenant_id, target_type, target_id):
        for rec in self._rows.values():
            if (
                rec.tenant_id == tenant_id
                and rec.target_type == target_type
                and rec.target_id == target_id
            ):
                return rec
        return None


def test_fake_store_implements_protocol():
    assert isinstance(_FakeMemoryStore(), MemoryStoreProtocol)


async def test_idempotent_persist_does_not_duplicate():
    store = _FakeMemoryStore()
    tid = uuid.UUID(int=1)
    pid = uuid.uuid4()
    inp = PersistLearningMemoryInput(
        tenant_id=tid, target_type="pattern", target_id=pid,
        signal={"action": "keep"}, provenance={"n": 1},
    )
    r1 = await store.persist(record=inp)
    r2 = await store.persist(record=inp)  # identical -> no-op
    assert r1.id == r2.id
    assert len(store.persisted) == 1  # noqa: PLR2004


async def test_persist_distinct_signal_appends():
    store = _FakeMemoryStore()
    tid = uuid.UUID(int=1)
    pid = uuid.uuid4()
    await store.persist(record=PersistLearningMemoryInput(
        tenant_id=tid, target_type="pattern", target_id=pid,
        signal={"action": "keep"}, provenance={"n": 1},
    ))
    await store.persist(record=PersistLearningMemoryInput(
        tenant_id=tid, target_type="pattern", target_id=pid,
        signal={"action": "deactivate"}, provenance={"n": 1},
    ))
    assert len(store.persisted) == 2  # noqa: PLR2004
