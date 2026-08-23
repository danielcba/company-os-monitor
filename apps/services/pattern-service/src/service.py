"""Pattern Detector - orchestration of the Generalize capability (R1).

Reads the tenant Context stream from Postgres (knowledge - the Reasoning layer
acts on knowledge, never directly on the world), runs the pure detection over
the Pattern Library, and persists the Candidate Patterns in ``patterns`` with
idempotent dedup. This component never writes to ``contexts``/``evidence``/
``observations`` (P1), never reads the observation bus, and never triggers
actions or alerts (R3: cognitive boundary; no action without Confidence, R4).
"""
import asyncio
from collections import Counter
from datetime import UTC, datetime

from libs.perception.context import ContextStore
from libs.procedural_memory.pattern_library import PATTERN_LIBRARY, PatternDefinition
from libs.reasoning.pattern import PatternCreate, PatternStore, build_pattern

from src.detector import detect


class PatternService:
    def __init__(
        self,
        context_store: ContextStore,
        pattern_store: PatternStore,
        library: tuple[PatternDefinition, ...] | list[PatternDefinition] = PATTERN_LIBRARY,
        window_days: float = 28.0,
    ):
        self.context_store = context_store
        self.pattern_store = pattern_store
        self.library = library
        self.window_days = window_days
        self.total_patterns = 0
        self.total_duplicates = 0
        self.total_below_threshold = 0
        self.errors = 0
        self.by_type: Counter[str] = Counter()
        self.by_mental_model: Counter[str] = Counter()
        self.last_run_at: datetime | None = None

    async def run_detection_cycle(self) -> int:
        """Detect patterns for every tenant with a Context stream.

        Processes tenants in parallel using asyncio.gather for horizontal
        scalability (each tenant is an independent data domain).
        """
        tenants = await self.context_store.list_tenant_ids()
        results = await asyncio.gather(
            *[self._detect_tenant(tenant_id) for tenant_id in tenants],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                self.errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.total_patterns

    async def _detect_tenant(self, tenant_id) -> None:
        """Detect patterns for a single tenant."""
        try:
            contexts = await self.context_store.list_contexts(tenant_id=tenant_id)
            result = detect(
                contexts,
                library=self.library,
                window_days=self.window_days,
                tenant_id=tenant_id,
            )
            self.total_below_threshold += result.below_threshold
            for candidate in result.candidates:
                await self._persist(tenant_id, candidate)
        except Exception:  # noqa: BLE001 - deliberate robustness per repo pattern
            self.errors += 1

    async def _persist(self, tenant_id, candidate) -> None:
        """Persist one Candidate Pattern (idempotent dedup, never an UPDATE)."""
        create = PatternCreate(
            tenant_id=tenant_id,
            context_id=candidate.context_id,
            pattern_type=candidate.pattern_type,
            description=candidate.description,
            strength_measure=candidate.strength_measure,
            frequency=candidate.frequency,
            library_pattern_id=candidate.library_pattern_id,
        )
        pattern = build_pattern(create)
        row = await self.pattern_store.save_pattern(pattern)
        if row is not None:
            self.total_patterns += 1
            self.by_type[pattern.pattern_type] += 1
            self.by_mental_model[candidate.mental_model_id] += 1
        else:
            self.total_duplicates += 1
