"""Anomaly Detector - orchestration of the Detect Deviation capability (R1).

Reads each tenant's Active Contexts and expected Patterns from Postgres
(knowledge - the Reasoning layer acts on knowledge, never directly on the
world), runs the pure detection over the Tolerance Library, and persists the
Candidate Anomalies in ``anomalies`` with idempotent dedup. This component
never writes to ``contexts``/``patterns``/``evidence``/``observations`` (P1),
never reads the observation bus, and never triggers actions or alerts (R3:
cognitive boundary; no action without Confidence, R4). It only signals a
measured deviation - it never explains it (that is Hypothesis).
"""
from collections import Counter
from datetime import UTC, datetime

from libs.perception.context import ContextStore
from libs.procedural_memory.tolerance_library import (
    TOLERANCE_LIBRARY,
    ToleranceDefinition,
)
from libs.reasoning.anomaly import AnomalyCreate, AnomalyStore, build_anomaly
from libs.reasoning.pattern import PatternStore

from src.detector import detect


class AnomalyService:
    def __init__(
        self,
        context_store: ContextStore,
        pattern_store: PatternStore,
        anomaly_store: AnomalyStore,
        tolerances: tuple[ToleranceDefinition, ...] | list[ToleranceDefinition] = TOLERANCE_LIBRARY,
    ):
        self.context_store = context_store
        self.pattern_store = pattern_store
        self.anomaly_store = anomaly_store
        self.tolerances = tolerances
        self.total_anomalies = 0
        self.total_duplicates = 0
        self.total_contexts_without_pattern = 0
        self.total_contexts_without_tolerance = 0
        self.errors = 0
        self.by_class: Counter[str] = Counter()
        self.by_mental_model: Counter[str] = Counter()
        self.last_run_at: datetime | None = None

    async def run_detection_cycle(self) -> int:
        """Detect deviations for every tenant with a Context stream."""
        tenants = await self.context_store.list_tenant_ids()
        for tenant_id in tenants:
            try:
                stream = await self.context_store.list_contexts(tenant_id=tenant_id)
                active = await self.context_store.list_active_contexts(tenant_id=tenant_id)
                patterns = await self.pattern_store.list_patterns(tenant_id=tenant_id)
                result = detect(
                    stream,
                    patterns,
                    self.tolerances,
                    active_contexts=active,
                    tenant_id=tenant_id,
                )
                self.total_contexts_without_pattern += result.contexts_without_pattern
                self.total_contexts_without_tolerance += result.contexts_without_tolerance
                for candidate in result.candidates:
                    await self._persist(tenant_id, candidate)
            except Exception:  # noqa: BLE001 - deliberate robustness per repo pattern
                self.errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.total_anomalies

    async def _persist(self, tenant_id, candidate) -> None:
        """Persist one Candidate Anomaly (idempotent dedup, never an UPDATE)."""
        create = AnomalyCreate(
            tenant_id=tenant_id,
            context_id=candidate.context_id,
            pattern_id=candidate.pattern_id,
            deviation_score=candidate.deviation_score,
            tolerance_threshold=candidate.tolerance_threshold,
            anomaly_class=candidate.anomaly_class,
        )
        anomaly = build_anomaly(create)
        row = await self.anomaly_store.save_anomaly(anomaly)
        if row is not None:
            self.total_anomalies += 1
            self.by_class[anomaly.anomaly_class] += 1
            self.by_mental_model[candidate.mental_model_id] += 1
        else:
            self.total_duplicates += 1