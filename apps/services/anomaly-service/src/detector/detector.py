"""Anomaly Detector - Reasoning/Detect Deviation capability (pure, no I/O).

Input: a tenant's Active Contexts (knowledge - never raw observations) + its
expected Patterns + the Tolerance Library (declarative thresholds). Transform:
compare each Active Context against the expected Pattern of its scope and
measure the magnitude of deviation. Output: Candidate Anomaly(s) with a
quantified ``deviation_score`` and the explicit ``tolerance_threshold``.

Detection scheme (documented and unit-tested):

* The expected Pattern for a scope ``(mental_model_id, purpose)`` is the most
  recent ``is_active`` ``patterns`` row whose anchor context (resolved through
  ``contexts`` by ``pattern.context_id``) shares that scope.
* Without an expected Pattern there is NO deviation - the context is counted in
  ``contexts_without_pattern`` and never emitted (the framework rule: anomaly
  detection is relative to patterns, never absolute).
* The tolerance for a scope is the ``ToleranceDefinition`` whose
  ``scope_mental_models``/``scope_purposes`` contain the scope and whose
  ``pattern_type`` matches the expected Pattern. Without one the context is
  counted in ``contexts_without_tolerance``.
* ``deviation_score`` follows the tolerance's ``deviation_spec``
  (``days_off_schedule`` or ``count_exceeding_window``, see the Tolerance
  Library for the exact formulas).
* A Candidate Anomaly is emitted only when ``deviation_score >
  tolerance.threshold``. ``anomaly_class`` is ``point`` in the MVP.
* The ``rationale`` is FACTUAL - it signals the measured deviation (a signal,
  never a conclusion). Causal or predictive explanation belongs to Hypothesis
  and is never produced here.

Idempotence: the same inputs produce the same Candidate Anomalies, whose
deterministic ``anomaly_id`` (see ``libs/reasoning/anomaly.py``) makes
re-runs deduplicate at the store layer.
"""
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from libs.perception.context import Context
from libs.procedural_memory.tolerance_library import (
    DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW,
    FREQUENCY_INTERVAL_DAYS,
    ToleranceDefinition,
)
from libs.reasoning.pattern import Pattern


@dataclass(frozen=True)
class CandidateAnomaly:
    """A measured deviation that exceeded its tolerance threshold."""

    context_id: uuid.UUID
    pattern_id: uuid.UUID
    mental_model_id: str
    purpose: str
    deviation_score: float
    tolerance_threshold: float
    anomaly_class: str
    tolerance_id: str
    deviation_spec: str
    rationale: str


@dataclass(frozen=True)
class DetectionResult:
    """Auditable outcome of one detection run over one tenant."""

    candidates: list[CandidateAnomaly]
    active_contexts: int
    contexts_without_pattern: int
    contexts_without_tolerance: int


def _resolve_pattern_scopes(
    patterns: Sequence[Pattern], anchors: dict[uuid.UUID, Context]
) -> dict[tuple[str, str], list[Pattern]]:
    """Group ``is_active`` patterns by the scope of their anchor context.

    A Pattern row does not persist mental_model_id/purpose; its scope is
    recovered through ``pattern.context_id`` -> anchor Context. Patterns whose
    anchor is unknown cannot be matched to an Active Context.
    """
    scoped: dict[tuple[str, str], list[Pattern]] = {}
    for pattern in patterns:
        if not pattern.is_active:
            continue
        anchor = anchors.get(pattern.context_id)
        if anchor is None:
            continue
        scope = (anchor.mental_model_id, anchor.purpose)
        scoped.setdefault(scope, []).append(pattern)
    for patterns_of_scope in scoped.values():
        patterns_of_scope.sort(key=lambda p: p.detected_at, reverse=True)
    return scoped


def _find_tolerance(
    tolerances: Sequence[ToleranceDefinition], ctx: Context, pattern_type: str
) -> ToleranceDefinition | None:
    for tolerance in tolerances:
        if ctx.mental_model_id not in tolerance.scope_mental_models:
            continue
        if tolerance.scope_purposes and ctx.purpose not in tolerance.scope_purposes:
            continue
        if tolerance.pattern_type != pattern_type:
            continue
        return tolerance
    return None


def _deviation_days_off_schedule(
    ctx: Context, pattern: Pattern
) -> float | None:
    """Ratio between the observed gap and the pattern's expected cadence.

    ``gap_days = (ctx.activated_at - pattern.detected_at)``; the score is
    ``abs(gap_days - interval) / interval`` where ``interval`` is the cadence
    mapped from the pattern's measured frequency label. Returns None when the
    pattern has no measured cadence (event-driven), so the tolerance cannot be
    applied.
    """
    interval = FREQUENCY_INTERVAL_DAYS.get(pattern.frequency)
    if interval is None:
        return None
    gap_days = (ctx.activated_at - pattern.detected_at).total_seconds() / 86400.0
    return abs(gap_days - interval) / interval


def _count_activations_in_window(
    ctx: Context,
    stream: Sequence[Context],
    tolerance: ToleranceDefinition,
) -> int:
    """Activations of the same scope inside ``[active.activated_at - window_days,
    active.activated_at]`` (the Active Context included), tenant-scoped."""
    window_start = ctx.activated_at - timedelta(days=tolerance.window_days)
    return sum(
        1
        for other in stream
        if other.tenant_id == ctx.tenant_id
        and other.mental_model_id == ctx.mental_model_id
        and other.purpose == ctx.purpose
        and window_start <= other.activated_at <= ctx.activated_at
    )


def _deviation_count_exceeding_window(
    ctx: Context,
    stream: Sequence[Context],
    tolerance: ToleranceDefinition,
) -> float:
    """Ratio between activations clustered in a short window and the max."""
    count = _count_activations_in_window(ctx, stream, tolerance)
    return count / max(tolerance.expected_max_activations, 1)


def _rationale_days_off_schedule(
    ctx: Context, pattern: Pattern, interval: float, score: float
) -> str:
    scope = f"{ctx.mental_model_id} para {ctx.purpose}"
    gap = (ctx.activated_at - pattern.detected_at).total_seconds() / 86400.0
    return (
        f"El contexto {scope} se activó el {ctx.activated_at:%Y-%m-%d %H:%M}; "
        f"el patrón esperado {pattern.id} (frecuencia {pattern.frequency}, "
        f"intervalo esperado de {interval:g} días desde "
        f"{pattern.detected_at:%Y-%m-%d %H:%M}) presenta una desviación de "
        f"{gap:+.1f} días respecto al intervalo esperado (score {score:g})."
    )


def _rationale_count_exceeding_window(
    ctx: Context, count: int, tolerance: ToleranceDefinition, score: float
) -> str:
    scope = f"{ctx.mental_model_id} para {ctx.purpose}"
    window_label = (
        int(tolerance.window_days)
        if tolerance.window_days.is_integer()
        else tolerance.window_days
    )
    return (
        f"El contexto {scope} se activó {count} veces en la ventana de "
        f"{window_label} día(s); el patrón esperado tolera como máximo "
        f"{tolerance.expected_max_activations} activación(es) en esa ventana "
        f"(score {score:g})."
    )


def detect(
    contexts: Sequence[Context],
    patterns: Sequence[Pattern],
    tolerances: Sequence[ToleranceDefinition],
    *,
    active_contexts: Sequence[Context] | None = None,
    tenant_id: uuid.UUID | None = None,
) -> DetectionResult:
    """Detect deviations of Active Contexts against expected Patterns (pure).

    ``contexts`` is the full Context stream for the tenant (used to resolve
    each pattern's scope and to count activations inside a window).
    ``active_contexts`` defaults to the ``is_active = true`` subset of
    ``contexts``. ``tenant_id`` optionally filters so the pure function is
    safe when handed mixed tenants.
    """
    if tenant_id is not None:
        contexts = [c for c in contexts if c.tenant_id == tenant_id]
        patterns = [p for p in patterns if p.tenant_id == tenant_id]

    anchors = {c.id: c for c in contexts}
    for ctx in active_contexts or ():
        anchors[ctx.id] = ctx

    if active_contexts is None:
        subjects = [c for c in contexts if c.is_active]
    else:
        subjects = [c for c in active_contexts if c.tenant_id == tenant_id]

    scoped_patterns = _resolve_pattern_scopes(patterns, anchors)

    candidates: list[CandidateAnomaly] = []
    without_pattern = 0
    without_tolerance = 0

    for ctx in subjects:
        scope = (ctx.mental_model_id, ctx.purpose)
        expected = scoped_patterns.get(scope)
        if not expected:
            without_pattern += 1
            continue
        pattern = expected[0]
        tolerance = _find_tolerance(tolerances, ctx, pattern.pattern_type)
        if tolerance is None:
            without_tolerance += 1
            continue

        if tolerance.deviation_spec == DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW:
            count = _count_activations_in_window(ctx, contexts, tolerance)
            score = _deviation_count_exceeding_window(ctx, contexts, tolerance)
            rationale = _rationale_count_exceeding_window(ctx, count, tolerance, score)
        else:
            score = _deviation_days_off_schedule(ctx, pattern)
            if score is None:
                without_tolerance += 1
                continue
            interval = FREQUENCY_INTERVAL_DAYS.get(pattern.frequency)
            rationale = _rationale_days_off_schedule(ctx, pattern, interval, score)

        if score > tolerance.threshold:
            candidates.append(
                CandidateAnomaly(
                    context_id=ctx.id,
                    pattern_id=pattern.id,
                    mental_model_id=ctx.mental_model_id,
                    purpose=ctx.purpose,
                    deviation_score=round(score, 4),
                    tolerance_threshold=round(tolerance.threshold, 4),
                    anomaly_class=tolerance.anomaly_class,
                    tolerance_id=tolerance.tolerance_id,
                    deviation_spec=tolerance.deviation_spec,
                    rationale=rationale,
                )
            )

    return DetectionResult(
        candidates=candidates,
        active_contexts=len(subjects),
        contexts_without_pattern=without_pattern,
        contexts_without_tolerance=without_tolerance,
    )