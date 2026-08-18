"""Pattern Detector - Reasoning/Generalize capability (pure functions, no I/O).

Input: a tenant's Context stream (knowledge; the detector never reads raw
observations) + a Pattern Library of declarative definitions. Transform:
measure the support of each known definition over the activation stream.
Output: Candidate Pattern(s) with ``strength_measure`` and ``frequency``.

Detection scheme (documented and unit-tested):

* For each ``PatternDefinition``, group the activations whose scope matches
  (``mental_model_id`` in ``scope_mental_models`` and, when declared,
  ``purpose`` in ``scope_purposes``) and whose ``activated_at`` falls inside
  the evaluation window ``[now - window_days, now]``.
* ``occurrences`` = number of activations of that group inside the window.
* ``strength_measure = min(occurrences / max(min_occurrences, 1), 1.0)``
  - 0.0 when the scope never appears in the window;
  - 1.0 once occurrences reach ``min_occurrences`` (support saturated).
* A Candidate Pattern is emitted only when
  ``strength_measure >= strength_threshold``. Groups that appear but stay below
  the threshold are counted for metrics (``below_threshold``); scopes that
  never appear are not evaluated.
* ``frequency`` is derived from the median interval (in days) between
  consecutive activations in the window:
    < 1/24 days   -> "hourly"
    <= 1 day      -> "daily"
    <= 7 days     -> "weekly"
    otherwise     -> "event-driven"
  When fewer than two activations are available the median is not measurable
  and the label falls back to "event-driven" (no interval observed).
* The candidate is anchored to the most recent activation of the group and its
  ``description`` is built from the definition template + the measured facts.

The output reports regularity only - never causal or predictive claims (P4:
patterns reveal regularity; explanations belong to Hypothesis).
"""
import itertools
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median

from libs.perception.context import Context
from libs.procedural_memory.pattern_library import PatternDefinition

FREQUENCY_HOURLY = "hourly"
FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"
FREQUENCY_EVENT_DRIVEN = "event-driven"


@dataclass(frozen=True)
class CandidatePattern:
    """A measured regularity that satisfied the definition's support threshold."""

    library_pattern_id: str
    pattern_type: str
    mental_model_id: str
    purpose: str
    context_id: uuid.UUID
    occurrences: int
    window_days: float
    median_interval_days: float | None
    frequency: str
    strength_measure: float
    description: str


@dataclass(frozen=True)
class DetectionResult:
    """Auditable outcome of one detection run over one tenant's stream."""

    candidates: list[CandidatePattern]
    evaluated: int
    below_threshold: int


def median_interval_days(activations: Sequence[Context]) -> float | None:
    """Median interval (in days) between consecutive activations, or None when
    fewer than two activations are available (not measurable)."""
    if len(activations) < 2:
        return None
    intervals = [
        (later.activated_at - earlier.activated_at).total_seconds() / 86400.0
        for earlier, later in itertools.pairwise(activations)
    ]
    return float(median(intervals))


def derive_frequency(activations: Sequence[Context]) -> tuple[float | None, str]:
    """Derive the frequency label from the measured median interval (in days)."""
    interval = median_interval_days(activations)
    if interval is None:
        return None, FREQUENCY_EVENT_DRIVEN
    if interval < 1 / 24:
        return interval, FREQUENCY_HOURLY
    if interval <= 1:
        return interval, FREQUENCY_DAILY
    if interval <= 7:
        return interval, FREQUENCY_WEEKLY
    return interval, FREQUENCY_EVENT_DRIVEN


def build_description(
    definition: PatternDefinition,
    *,
    scope: str,
    occurrences: int,
    window_days: float,
    median_interval_days: float | None,
) -> str:
    """Fill the definition's factual template with the measured facts."""
    window_label = (
        int(window_days) if float(window_days).is_integer() else window_days
    )
    facts = {
        "scope": scope,
        "occurrences": occurrences,
        "window_days": window_label,
        "median_interval": (
            f"{median_interval_days:.1f}" if median_interval_days is not None else "no medible"
        ),
    }
    return definition.description_template.format(**facts)


def detect(
    contexts: Sequence[Context],
    library: Sequence[PatternDefinition],
    window_days: float,
    *,
    now: datetime | None = None,
    tenant_id: uuid.UUID | None = None,
) -> DetectionResult:
    """Detect recurrent regularities over a Context stream (pure, no I/O).

    ``now`` defaults to the current UTC time and may be pinned for
    deterministic tests. ``tenant_id`` optionally filters the stream so the
    pure function is safe when handed mixed tenants.
    """
    if tenant_id is not None:
        contexts = [c for c in contexts if c.tenant_id == tenant_id]
    reference = now if now is not None else datetime.now(UTC)
    cutoff = reference - timedelta(days=window_days)
    windowed = [
        c for c in contexts if cutoff <= c.activated_at <= reference
    ]

    candidates: list[CandidatePattern] = []
    evaluated = 0
    below_threshold = 0

    for definition in library:
        groups: dict[tuple[str, str], list[Context]] = {}
        for ctx in windowed:
            if ctx.mental_model_id not in definition.scope_mental_models:
                continue
            if definition.scope_purposes and ctx.purpose not in definition.scope_purposes:
                continue
            groups.setdefault((ctx.mental_model_id, ctx.purpose), []).append(ctx)

        for (mental_model_id, purpose), acts in groups.items():
            acts = sorted(acts, key=lambda c: c.activated_at)
            occurrences = len(acts)
            strength = min(occurrences / max(definition.min_occurrences, 1), 1.0)
            evaluated += 1
            if strength < definition.strength_threshold:
                below_threshold += 1
                continue
            median_days, frequency = derive_frequency(acts)
            anchor = acts[-1]
            description = build_description(
                definition,
                scope=f"{mental_model_id} para {purpose}",
                occurrences=occurrences,
                window_days=window_days,
                median_interval_days=median_days,
            )
            candidates.append(
                CandidatePattern(
                    library_pattern_id=definition.pattern_id,
                    pattern_type=definition.pattern_type,
                    mental_model_id=mental_model_id,
                    purpose=purpose,
                    context_id=anchor.id,
                    occurrences=occurrences,
                    window_days=window_days,
                    median_interval_days=median_days,
                    frequency=frequency,
                    strength_measure=round(strength, 4),
                    description=description,
                )
            )

    return DetectionResult(
        candidates=candidates,
        evaluated=evaluated,
        below_threshold=below_threshold,
    )
