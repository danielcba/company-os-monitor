"""Confidence Calibration (Learning family) - wired by the Confidence Service.

Implements the Calibration Model of the Confidence concept (core-concepts/
confidence.md): evidential support, explanatory coherence, Brier score, ECE and
final confidence. The ``confidence-service`` (Sprint 8) is the single consumer
of this module: it computes a calibrated ``confidence_score`` (C_final) for each
judgment under evaluation (Hypothesis today; Recommendation/Decision in later
sprints), persisting the row in ``confidence_scores``.

The module follows the concept's rules: Confidence is computed, not intuited;
the score is a calibrated reliability estimate, never a feeling; parameters
(alpha, M, L0) are fixed a priori and published with every report; the
calibration factor is measured from outcomes only and is never adjusted to
justify a particular confidence (falsifiability).

``QUALITY_CLASS_RANGES`` are the canonical Q1-Q4 score bands (docs/02). The
Organize capability picks the midrange weight of each band at Evidence creation
-- see collector-service organizer/engine.py. Bands are NOT the same thing as
the organizer's assigned weights; ``quality_class_to_weight`` keeps the
canonical band mapping here so the calibrator derives evidential weights
directly from the Quality Class of each Evidence.
"""
from dataclasses import dataclass
from math import exp


@dataclass(frozen=True)
class CalibrationParams:
    alpha: float = 0.5      # mixing coefficient
    M: int = 10             # ECE bins
    L0: float = 0.0         # prior log-odds

QUALITY_CLASS_RANGES: dict[str, tuple[float, float]] = {
    "Q1": (0.75, 1.0),
    "Q2": (0.50, 0.75),
    "Q3": (0.25, 0.50),
    "Q4": (0.00, 0.25),
}

def quality_class_to_weight(qc: str) -> float:
    """Convert quality class to mid-point weight for calibration.

    Raises:
        ValueError: If quality class is not one of Q1, Q2, Q3, Q4.
    """
    try:
        low, high = QUALITY_CLASS_RANGES[qc]
    except KeyError:
        raise ValueError(f"Unknown quality class: {qc!r}. Expected one of {sorted(QUALITY_CLASS_RANGES)}")
    return (low + high) / 2

def evidential_support(evidence_weights: list[float], signs: list[int], L0: float = 0.0) -> float:
    """S(H|E) = 1 / (1 + e^-L), L = L0 + sum(w_i * e_i)

    Uses strict=True to catch length mismatches (Python 3.10+).
    """
    L = L0 + sum(w * e for w, e in zip(evidence_weights, signs, strict=True))
    return 1.0 / (1.0 + exp(-L))

def explanatory_coherence(evidence: list[str], constraints: dict) -> float:
    """C(H) - normalized constraint satisfaction (Thagard, 1989), real implementation.

    The coherence score C(H) in [0, 1] is computed as normalized constraint
    satisfaction over positive and negative constraints, following the
    explanatory coherence program (Thagard, 1989) as specified by the
    Confidence concept: C(H) measures the fraction of the scope evidence the
    hypothesis explains, penalized by evidence it contradicts and by scope
    evidence it does not explain.

    Constraint schema (``constraints``, documented and stable):
      ``explains``:        list[str] - evidence (organization_type or fact label)
                           the hypothesis explains (positive constraint).
      ``contradicts``:     list[str] - evidence the hypothesis contradicts
                           (negative constraint; a declared contradiction that
                           is present in the scope counts against C).
      ``coherent_with``:   list[str] - other hypotheses of the scope consistent
                           with H (positive hypothesis-to-hypothesis constraint).
      ``incoherent_with``: list[str] - competing hypotheses inconsistent with H
                           (negative hypothesis-to-hypothesis constraint).

    ``evidence`` is the scope evidence present in the batch (the current data),
    as organization_type / fact labels.

    MVP normalization (documented simplification):
        C(H) = P / (P + N + U)
    where
        P = |explains ∩ scope| + |coherent_with|   (satisfied positive constraints)
        N = |contradicts ∩ scope| + |incoherent_with| (violated negative constraints)
        U = |scope \\ (explains ∪ contradicts)|     (scope evidence H neither explains nor contradicts)
    Clamped to [0, 1]. A hypothesis that explains its full scope and contradicts
    nothing scores 1.0; one that contradicts everything and explains nothing
    scores 0.0. With no scope evidence the score is the neutral 0.5 (no facts to
    evaluate, documented) rather than an invented confidence.
    """
    scope = set(evidence)
    if not scope:
        return 0.5
    explains = set(constraints.get("explains", []))
    contradicts = set(constraints.get("contradicts", []))
    coherent_with = set(constraints.get("coherent_with", []))
    incoherent_with = set(constraints.get("incoherent_with", []))

    explained = len(explains & scope)
    contradicted = len(contradicts & scope)
    # U = scope evidence that H neither explains nor contradicts
    unexplained = len(scope - (explains | contradicts))
    positive = explained + len(coherent_with)
    negative = contradicted + len(incoherent_with)
    total = positive + negative + unexplained
    if total == 0:
        return 0.5
    return max(0.0, min(1.0, positive / total))

def brier_score(predictions: list[float], outcomes: list[int]) -> float:
    if not predictions:
        return 0.0
    return sum((p - o) ** 2 for p, o in zip(predictions, outcomes, strict=True)) / len(predictions)

def ece_score(predictions: list[float], outcomes: list[int], M: int = 10) -> float:
    """ECE over M bins. The last bin includes p == 1.0 (a prediction of exactly
    1.0 must be counted, not dropped from every bin while staying in the
    denominator)."""
    if not predictions:
        return 0.0
    bin_edges = [i / M for i in range(M + 1)]
    ece = 0.0
    for m in range(M):
        lower, upper = bin_edges[m], bin_edges[m + 1]
        last = m == M - 1
        bin_preds = [
            p
            for p in predictions
            if lower <= p and (p < upper or (last and p <= upper))
        ]
        if not bin_preds:
            continue
        bin_outcomes = [
            o
            for p, o in zip(predictions, outcomes, strict=True)
            if lower <= p and (p < upper or (last and p <= upper))
        ]
        acc = sum(bin_outcomes) / len(bin_outcomes)
        conf = sum(bin_preds) / len(bin_preds)
        ece += (len(bin_preds) / len(predictions)) * abs(acc - conf)
    return ece

def final_confidence(S: float, C: float, ECE: float, alpha: float = 0.5) -> float:
    """C_final = [alpha*S + (1-alpha)*C] * (1 - ECE)

    Validates and clamps inputs to [0, 1] range.
    """
    if not 0.0 <= S <= 1.0:
        raise ValueError(f"S (evidential_support) must be in [0, 1], got {S}")
    if not 0.0 <= C <= 1.0:
        raise ValueError(f"C (explanatory_coherence) must be in [0, 1], got {C}")
    if not 0.0 <= ECE <= 1.0:
        raise ValueError(f"ECE must be in [0, 1], got {ECE}")
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha}")
    return max(0.0, min(1.0, (alpha * S + (1 - alpha) * C) * (1 - ECE)))