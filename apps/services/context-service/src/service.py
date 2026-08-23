"""Context Activator - orchestration of the Explain capability (R1).

Reads immutable Evidence from Postgres (input), runs the explanatory coherence
competition per tenant + purpose, and persists the selected Active Context in
``contexts`` (idempotent dedup; supersedes the previous active context of the
same tenant+purpose). This component never organizes Evidence nor reasons about
patterns (R3) - it only selects the most coherent interpretation (P2).
"""
import asyncio
from collections import Counter
from datetime import UTC, datetime

from libs.perception.context import PURPOSES, ContextStore, build_context
from libs.perception.evidence import EvidenceStore

from src.activator import ActivatorEngine


class ContextService:
    def __init__(
        self,
        evidence_store: EvidenceStore,
        context_store: ContextStore,
        engine: ActivatorEngine | None = None,
        purposes: set[str] | None = None,
    ):
        self.evidence_store = evidence_store
        self.context_store = context_store
        self.engine = engine or ActivatorEngine()
        self.purposes = purposes or set(PURPOSES)
        self.contexts_activated = 0
        self.contexts_duplicates = 0
        self.errors = 0
        self.by_mental_model: Counter[str] = Counter()
        self.by_purpose: Counter[str] = Counter()
        self.last_run_at: datetime | None = None

    async def run_activation_cycle(self) -> int:
        """Activate contexts for every tenant with evidence across all purposes.

        Processes tenants in parallel using asyncio.gather for horizontal
        scalability (each tenant is an independent data domain).
        """
        tenants = await self.evidence_store.list_tenant_ids()
        results = await asyncio.gather(
            *[self._activate_tenant(tenant_id) for tenant_id in tenants],
            return_exceptions=True,
        )
        # Count exceptions from gather.
        for result in results:
            if isinstance(result, Exception):
                self.errors += 1
        self.last_run_at = datetime.now(UTC)
        return self.contexts_activated

    async def _activate_tenant(self, tenant_id) -> None:
        """Activate contexts for a single tenant across all purposes."""
        evidence = await self.evidence_store.list_evidence(tenant_id=tenant_id)
        for purpose in sorted(self.purposes):
            try:
                await self._activate(tenant_id, evidence, purpose)
            except Exception:  # noqa: BLE001 - deliberate robustness per repo pattern
                self.errors += 1

    async def _activate(
        self, tenant_id, evidence, purpose: str
    ) -> None:
        """Run one competition and persist the selected Active Context."""
        create = self.engine.activate(evidence, purpose)
        if create is None or create.tenant_id != tenant_id:
            return
        context = build_context(create)
        row = await self.context_store.save_context(context)
        if row is not None:
            self.contexts_activated += 1
            self.by_mental_model[context.mental_model_id] += 1
            self.by_purpose[context.purpose] += 1
        else:
            self.contexts_duplicates += 1