"""Context Activator - Perception/Explain capability.

Pure module: computes the explanatory coherence competition (P2) among the
compatible mental models for a purpose over a batch of immutable Evidence.
Context is selected, never generated: the winner is the model that explains
the largest share of the available weighted evidence, and every candidate
(with its score) is kept for traceability.
"""
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from libs.perception.context import MentalModel, models_for_purpose
from libs.perception.evidence import Evidence


@dataclass(frozen=True)
class ModelScore:
    """Coherence of one mental model against a batch of evidence."""

    mental_model_id: str
    coherence_score: float
    explained_weight: float
    explained_count: int


@dataclass(frozen=True)
class CompetitionResult:
    """Auditable outcome of the coherence competition (P2)."""

    purpose: str
    winner: ModelScore
    candidates: list[ModelScore]
    evidence_ids: list[uuid.UUID]


def weights_by_type(evidence: Sequence[Evidence]) -> dict[str, float]:
    """Accumulate evidential weight per organization_type (from quality class)."""
    result: dict[str, float] = {}
    for item in evidence:
        result[item.organization_type] = result.get(item.organization_type, 0.0) + item.weight
    return result


def total_weight(evidence: Sequence[Evidence]) -> float:
    return sum(item.weight for item in evidence)


def score_model(
    model: MentalModel, weights: dict[str, float], total: float
) -> ModelScore:
    """Coherence = explained evidential weight / available evidential weight.

    Only matching of evidence organization_types with the model's declarative
    signature - no interpretation, no causal claim (P2). A model that explains
    no evidence in the batch scores 0.
    """
    explained_weight = sum(weights.get(fact_type, 0.0) for fact_type in model.explains)
    explained_count = sum(1 for fact_type in model.explains if fact_type in weights)
    score = explained_weight / total if total > 0 else 0.0
    return ModelScore(
        mental_model_id=model.model_id,
        coherence_score=score,
        explained_weight=explained_weight,
        explained_count=explained_count,
    )


def compete(
    evidence: Sequence[Evidence],
    purpose: str,
    models: Sequence[MentalModel] | None = None,
) -> CompetitionResult | None:
    """Run the coherence competition for one purpose over one evidence batch.

    Returns None when there is no evidence (nothing to explain) or no candidate
    model is compatible with the purpose. Only models whose declared purposes
    include ``purpose`` compete. Candidates are sorted by descending coherence;
    ties are resolved deterministically by model id (documented decision, so
    re-runs are stable and auditable).
    """
    candidates = [
        model
        for model in (list(models) if models is not None else models_for_purpose(purpose))
        if purpose in model.purposes
    ]
    if not evidence or not candidates:
        return None
    total = total_weight(evidence)
    weights = weights_by_type(evidence)
    scores = [score_model(model, weights, total) for model in candidates]
    scores.sort(key=lambda score: (-score.coherence_score, score.mental_model_id))
    return CompetitionResult(
        purpose=purpose,
        winner=scores[0],
        candidates=scores,
        evidence_ids=[item.id for item in evidence],
    )
