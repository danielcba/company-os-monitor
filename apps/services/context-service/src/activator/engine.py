"""Context Activator Engine - pure orchestration of the coherence competition.

Combines the declarative mental-model catalogue with the pure scoring in
``coherence`` to produce a ``ContextCreate`` for a tenant + purpose. No I/O:
the evidence batch is passed in (immutable rows) and the winner is derived by
competition (P2), never by direct interpretation.
"""
from collections.abc import Sequence

from libs.perception.context import (
    MENTAL_MODEL_CATALOG,
    ContextCreate,
    MentalModel,
)
from libs.perception.evidence import Evidence

from src.activator.coherence import compete


class ActivatorEngine:
    """Build the Active Context request from an evidence batch + purpose."""

    def __init__(self, models: Sequence[MentalModel] | None = None):
        self.models = list(models) if models is not None else MENTAL_MODEL_CATALOG

    def activate(self, evidence: list[Evidence], purpose: str) -> ContextCreate | None:
        """Return the ContextCreate for the winning model, or None when the
        batch cannot be explained (no evidence / no compatible candidates)."""
        result = compete(evidence, purpose, models=self.models)
        if result is None:
            return None
        return ContextCreate(
            tenant_id=evidence[0].tenant_id,
            evidence_ids=result.evidence_ids,
            mental_model_id=result.winner.mental_model_id,
            purpose=purpose,
            coherence_score=round(result.winner.coherence_score, 2),
            competing_models=[
                {
                    "mental_model_id": candidate.mental_model_id,
                    "coherence_score": round(candidate.coherence_score, 2),
                }
                for candidate in result.candidates
            ],
        )