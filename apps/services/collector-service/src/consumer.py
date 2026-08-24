"""Evidence Organizer - consume immutable Observations, persist them (append-only)
and organize them into Evidence.

Observations are never modified here (P1). A message is acknowledged on the
stream only after the INSERT succeeds; failures stay pending for retry. After
persisting a batch, the domain organization rules run over the buffered
observations (per tenant, within the longest rule window) and the resulting
Evidence rows are inserted idempotently (deterministic id + ON CONFLICT).
"""
from collections import Counter
from datetime import UTC, datetime, timedelta

from libs.cognitive_core.observation_bus import Observation, ObservationBus
from libs.perception.evidence import EvidenceStore, build_evidence
from libs.perception.store import ObservationStore

from src.organizer import OrganizerConfig, OrganizerEngine


class ObservationConsumer:
    def __init__(
        self,
        bus: ObservationBus,
        store: ObservationStore,
        group: str = "evidence_organizers",
        consumer: str = "collector-1",
        evidence_store: EvidenceStore | None = None,
        organizer: OrganizerEngine | None = None,
    ):
        self.bus = bus
        self.store = store
        self.group = group
        self.consumer = consumer
        self.evidence_store = evidence_store
        self.organizer = organizer or OrganizerEngine(OrganizerConfig())
        self.processed = 0
        self.errors = 0
        self.duplicates = 0
        self.last_processed_at: datetime | None = None
        self.evidence_created = 0
        self.evidence_duplicates = 0
        self.evidence_errors = 0
        self.evidence_by_type: Counter[str] = Counter()
        self._pending: list[Observation] = []

    async def _persist(self, observation: Observation) -> bool:
        """Persist one observation. Returns True when already present (duplicate)."""
        exists = await self.store.observation_exists(
            id=observation.id, captured_at=observation.captured_at
        )
        if exists:
            return True
        await self.store.save_observation(observation)
        return False

    def _prune_pending(self) -> None:
        """Keep only observations inside the longest rule window of the newest one."""
        if not self._pending:
            return
        latest = max(obs.captured_at for obs in self._pending)
        cutoff = latest - timedelta(minutes=self.organizer.config.max_window_minutes)
        self._pending = [
            obs for obs in self._pending if obs.captured_at >= cutoff
        ]

    async def _organize(self) -> None:
        """Run the organization rules over buffered observations (dedup idempotent)."""
        if self.evidence_store is None:
            return
        self._prune_pending()
        try:
            creations = self.organizer.organize(self._pending)
            for create in creations:
                evidence = build_evidence(create)
                row = await self.evidence_store.save_evidence(evidence)
                if row is not None:
                    self.evidence_created += 1
                    self.evidence_by_type[evidence.organization_type] += 1
                else:
                    self.evidence_duplicates += 1
        except Exception:  # noqa: BLE001
            self.evidence_errors += 1

    async def process_batch(self, count: int = 100, block_ms: int = 5000) -> int:
        """Consume one batch and return how many observations were processed."""
        processed = 0
        async for msg_id, observation in self.bus.consume(
            self.group, self.consumer, count=count, block_ms=block_ms
        ):
            try:
                duplicate = await self._persist(observation)
                if duplicate:
                    self.duplicates += 1
                await self.bus.ack(self.group, msg_id)
                self.processed += 1
                processed += 1
                self.last_processed_at = datetime.now(UTC)
                self._pending.append(observation)
            except Exception:  # noqa: BLE001 - consumer loop: count errors and continue processing
                self.errors += 1
        await self._organize()
        return processed