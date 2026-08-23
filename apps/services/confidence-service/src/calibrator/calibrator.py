"""Confidence Calibrator - Learning/Calibrate capability (pure functions, no I/O).

Implements the Confidence concept's Calibration Model for one judgment under
evaluation (a Hypothesis in this phase; Recommendation/Decision in Sprints 9/10)
and produces the ``ConfidenceCreate`` persisted by the Confidence Store:

    S(H|E)   = sigmoid(L0 + sum(w_i*e_i))      evidential support
    C(H)     = explanatory_coherence(...)      normalized constraint satisfaction
    ECE      = ece_score(history, M)           calibration error (0 if no history)
    C_final  = [alpha*S + (1-alpha)*C] * (1 - ECE)

Parameters (alpha, M, L0) come from ``CalibrationParams`` - fixed a priori and
always published in ``calibration_justification`` together with S, C and ECE
(first-class explanation). The calibration factor (1 - ECE) is measured from
outcomes only and never adjusted to justify a particular confidence: identical
inputs always produce identical scores (anti-tuning, pure deterministic
functions) and the calibration can be audited post hoc (falsifiability).
"""
import uuid
from collections.abc import Sequence

from libs.cognitive_core.calibration_model import (
    CalibrationParams,
    ece_score,
    evidential_support,
    explanatory_coherence,
    final_confidence,
    quality_class_to_weight,
)
from libs.learning.confidence import ConfidenceCreate
from libs.perception.context import Context
from libs.perception.evidence import Evidence
from libs.reasoning.anomaly import Anomaly
from libs.reasoning.hypothesis import Hypothesis

TARGET_TYPE_HYPOTHESIS = "hypothesis"


def _sign(evidence_type: str, explains: set[str], contradicts: set[str]) -> int:
    """Evidential sign of one evidence for the judgment (documented scheme).

    +1 when the organization_type is declared in ``explains`` (supports),
    -1 when in ``contradicts`` (opposes), 0 otherwise (neutral: not all tenant
    evidence is relevant to a given judgment).

    Uses pre-computed sets for O(1) lookup.
    """
    if evidence_type in explains:
        return 1
    if evidence_type in contradicts:
        return -1
    return 0


def _get_sign_sets(coherence_inputs: dict) -> tuple[set[str], set[str]]:
    """Extract and convert explains/contradicts to sets for O(1) lookup."""
    return (
        set(coherence_inputs.get("explains", [])),
        set(coherence_inputs.get("contradicts", [])),
    )


def evidential_support_score(
    evidence: Sequence[Evidence], coherence_inputs: dict, L0: float = 0.0
) -> float:
    """S(H|E) from the evidence Quality Classes and their +/- signs.

    Only evidence declared in ``explains`` (+1) or ``contradicts`` (-1)
    contributes to the log-odds; neutral evidence is excluded. Weights are the
    canonical band midpoints (``quality_class_to_weight``), as the Calibration
    Model derives w_i from the Quality Class. With no contributing evidence
    S = 0.5 (uniform prior, L = L0 = 0).
    """
    explains, contradicts = _get_sign_sets(coherence_inputs)
    weights: list[float] = []
    signs: list[int] = []
    for item in evidence:
        sign = _sign(item.organization_type, explains, contradicts)
        if sign == 0:
            continue
        weights.append(quality_class_to_weight(item.quality_class.value))
        signs.append(sign)
    return evidential_support(weights, signs, L0)


def coherence_score(
    judgment: str, scope: Sequence[Evidence], coherence_inputs: dict
) -> float:
    """C(H) - explanatory coherence of the judgment over the scope evidence."""
    return explanatory_coherence(
        [item.organization_type for item in scope], coherence_inputs
    )


def historical_calibration_factor(
    historical: Sequence[tuple[float, int]] | None, M: int = 10
) -> tuple[float, float]:
    """``(1 - ECE, ECE)`` for the judgment class, measured from outcomes only.

    ``historical`` is ``(reported_confidence, outcome)`` pairs, outcome in
    {0, 1}. Without history the factor is ``(1.0, 0.0)``: the first data points
    are not yet penalized (documented) and the model stays falsifiable once
    outcomes arrive. The factor is never adjusted to justify a confidence.
    """
    if not historical:
        return 1.0, 0.0
    predictions = [p for p, _ in historical]
    outcomes = [o for _, o in historical]
    ece = ece_score(predictions, outcomes, M)
    return max(0.0, min(1.0, 1.0 - ece)), ece


def resolve_scope_evidence(
    hypothesis: Hypothesis,
    anomalies: Sequence[Anomaly],
    contexts: Sequence[Context],
    evidence_by_id: dict[uuid.UUID, Evidence],
) -> list[Evidence]:
    """The evidence a hypothesis is accountable for (its factual scope).

    Follows the traceability chain hypothesis -> anomaly (``anomaly_ids``) ->
    context (``anomaly.context_id``) -> evidence (``context.evidence_ids``).
    Pure: reads the pre-loaded P1 immutable objects; never writes.
    """
    anomaly_ids = set(hypothesis.anomaly_ids)
    ctx_ids = {a.context_id for a in anomalies if a.id in anomaly_ids}
    ev_ids = {
        eid for c in contexts if c.id in ctx_ids for eid in c.evidence_ids
    }
    return [evidence_by_id[eid] for eid in ev_ids if eid in evidence_by_id]


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def _justification(
    judgment: str,
    S: float,
    C: float,
    ece: float,
    hist: float,
    params: CalibrationParams,
    supporting: Sequence[Evidence],
    opposing: Sequence[Evidence],
    coherence_inputs: dict,
    historical: Sequence[tuple[float, int]] | None,
) -> str:
    """First-class, auditable reasons for the score (S, C, ECE, params)."""
    support_desc = ", ".join(
        f"{item.organization_type} "
        f"(Q{item.quality_class.value}, "
        f"w={_fmt(quality_class_to_weight(item.quality_class.value))})"
        for item in supporting
    ) or "ninguna"
    oppose_desc = ", ".join(item.organization_type for item in opposing) or "ninguna"
    history_desc = (
        f"{len(historical)} outcomes historicos"
        if historical
        else "sin historial de outcomes (primeros datos)"
    )
    l_odds = params.L0 + sum(
        quality_class_to_weight(item.quality_class.value) for item in supporting
    ) - sum(quality_class_to_weight(item.quality_class.value) for item in opposing)
    c_final = final_confidence(S, C, ece, params.alpha)
    return (
        f"Confidence calibrada para {judgment[:120]!r}. "
        f"Parametros fijos a priori (nunca tunificados): alpha={_fmt(params.alpha)}, "
        f"M={params.M}, L0={_fmt(params.L0)}. "
        f"S(H|E)={_fmt(S)} (log-odds L={_fmt(l_odds)}; apoya: {support_desc}; "
        f"contradice: {oppose_desc}). "
        f"C(H)={_fmt(C)} (satisfaccion de constraints normalizada; "
        f"explains={sorted(coherence_inputs.get('explains', []))}, "
        f"contradicts={sorted(coherence_inputs.get('contradicts', []))}). "
        f"ECE={_fmt(ece)} ({history_desc}); historical_calibration=1-ECE={_fmt(hist)}. "
        f"C_final=[{_fmt(params.alpha)}*{_fmt(S)}+"
        f"{_fmt(1 - params.alpha)}*{_fmt(C)}]*{_fmt(hist)}={_fmt(c_final)}. "
        f"El factor de calibracion se mide solo de outcomes; nunca se ajusta "
        f"para justificar una confianza particular."
    )


def calibrate(
    hypothesis: Hypothesis,
    evidence: Sequence[Evidence],
    scope: Sequence[Evidence],
    coherence_inputs: dict,
    params: CalibrationParams,
    historical: Sequence[tuple[float, int]] | None,
) -> ConfidenceCreate:
    """Calibrate one judgment (a Hypothesis) and build its ConfidenceCreate.

    Computes S(H|E), C(H), the (1 - ECE) factor and C_final with the fixed
    params, and always attaches a justification documenting S, C, ECE, alpha,
    M and L0. Target context (tenant_id, target_type='hypothesis', target_id)
    is taken from the ``hypothesis`` object. Action Layer targets
    (recommendation/decision, Sprints 9/10) reuse the same components through
    the same ConfidenceCreate/ConfidenceStore path (the API is target-ready).

    The ``historical`` parameter is reserved for future outcome-based calibration
    (Sprint 9+). Currently always None; when available, it should contain
    (reported_confidence, outcome) pairs where outcome in {0, 1}.
    """
    # Input validation
    if hypothesis is None:
        raise ValueError("hypothesis must not be None")
    if not evidence:
        raise ValueError("evidence sequence must not be empty")
    if not scope:
        raise ValueError("scope sequence must not be empty")
    if params is None:
        raise ValueError("params must not be None")
    if not 0.0 <= params.alpha <= 1.0:
        raise ValueError(f"params.alpha must be in [0, 1], got {params.alpha}")
    if params.M <= 0:
        raise ValueError(f"params.M must be positive, got {params.M}")

    S = evidential_support_score(evidence, coherence_inputs, params.L0)
    C = coherence_score(hypothesis.description, scope, coherence_inputs)
    hist, ece = historical_calibration_factor(historical, params.M)
    c_final = final_confidence(S, C, ece, params.alpha)
    explains, contradicts = _get_sign_sets(coherence_inputs)
    supporting = [
        item for item in evidence if _sign(item.organization_type, explains, contradicts) == 1
    ]
    opposing = [
        item for item in evidence if _sign(item.organization_type, explains, contradicts) == -1
    ]
    justification = _justification(
        hypothesis.description,
        S,
        C,
        ece,
        hist,
        params,
        supporting,
        opposing,
        coherence_inputs,
        historical,
    )
    return ConfidenceCreate(
        tenant_id=hypothesis.tenant_id,
        target_type=TARGET_TYPE_HYPOTHESIS,
        target_id=hypothesis.id,
        evidential_support=S,
        explanatory_coherence=C,
        historical_calibration=hist,
        confidence_score=c_final,
        alpha=params.alpha,
        calibration_justification=justification,
        calibration_error_estimate=ece,
    )