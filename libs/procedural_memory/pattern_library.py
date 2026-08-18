"""Pattern Library - declarative definitions of known patterns (Reasoning/Generalize).

The Pattern Library is procedural memory (P3): a catalogue of *known* patterns
expressed as declarative definitions, never reasoning and never ML. Per P4 a
pattern is a "working regularity": revising one means publishing a NEW version
of the definition (``pattern_id`` suffix ``_v2``), never mutating a published
version nor running an UPDATE on ``patterns`` rows.

The library only declares the scope each definition covers and the minimum
support required; it never detects anything by itself (the detector in
``pattern-service`` does the measurement).
"""
from dataclasses import dataclass, field

# Pattern types reserved by the architecture. The Sprint 5 MVP implements only
# ``temporal`` (recurrence over the context stream); correlation, sequential
# and threshold are reserved for later Reasoning sprints and must not be used.
PATTERN_TYPE_TEMPORAL = "temporal"
PATTERN_TYPE_CORRELATION = "correlation"
PATTERN_TYPE_SEQUENTIAL = "sequential"
PATTERN_TYPE_THRESHOLD = "threshold"
PATTERN_TYPES: frozenset[str] = frozenset(
    {
        PATTERN_TYPE_TEMPORAL,
        PATTERN_TYPE_CORRELATION,
        PATTERN_TYPE_SEQUENTIAL,
        PATTERN_TYPE_THRESHOLD,
    }
)

FREQUENCY_LABELS: frozenset[str] = frozenset(
    {"daily", "weekly", "hourly", "event-driven"}
)


@dataclass(frozen=True)
class PatternDefinition:
    """Declarative definition of a known pattern (procedural memory, P3).

    ``scope_mental_models`` restricts which mental models the definition
    applies to; ``scope_purposes`` restricts the purposes (empty frozenset =
    all purposes). ``min_occurrences`` is the reference for the support measure
    (strength = occurrences_in_window / max(min_occurrences, 1), saturated at
    1.0) and ``strength_threshold`` is the minimum strength a candidate must
    reach to be emitted. ``description_template`` is a FACTUAL template over
    the measured facts (``{scope}``, ``{occurrences}``, ``{window_days}``,
    ``{median_interval}``) - never causal or predictive language (P4).
    """

    pattern_id: str
    pattern_type: str = PATTERN_TYPE_TEMPORAL
    domain: str = ""
    scope_mental_models: frozenset[str] = field(default_factory=frozenset)
    scope_purposes: frozenset[str] = field(default_factory=frozenset)
    min_occurrences: int = 3
    strength_threshold: float = 0.6
    frequency_label: str = "event-driven"
    description_template: str = (
        "El contexto {scope} se activó {occurrences} veces en la ventana "
        "de {window_days} días (intervalo mediano ~{median_interval} días). "
        "Regularidad detectada."
    )

    def __post_init__(self) -> None:
        if self.pattern_type not in PATTERN_TYPES:
            raise ValueError(f"unknown pattern_type: {self.pattern_type}")  # noqa: TRY003
        if not 0.0 <= self.strength_threshold <= 1.0:
            raise ValueError("strength_threshold must be in [0, 1]")  # noqa: TRY003
        if self.frequency_label not in FREQUENCY_LABELS:
            raise ValueError(f"unknown frequency_label: {self.frequency_label}")  # noqa: TRY003
        if self.min_occurrences < 1:
            raise ValueError("min_occurrences must be >= 1")  # noqa: TRY003


PATTERN_LIBRARY: tuple[PatternDefinition, ...] = (
    PatternDefinition(
        pattern_id="context_recurrence_capacity_risk_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        domain="capacity",
        scope_mental_models=frozenset({"capacity_risk"}),
        min_occurrences=3,
        strength_threshold=0.6,
        frequency_label="weekly",
        description_template=(
            "El contexto {scope} se activó {occurrences} veces en la ventana "
            "de {window_days} días (intervalo mediano ~{median_interval} días). "
            "Regularidad detectada."
        ),
    ),
    PatternDefinition(
        pattern_id="context_recurrence_service_failure_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        domain="service",
        scope_mental_models=frozenset({"service_failure"}),
        min_occurrences=3,
        strength_threshold=0.6,
        frequency_label="event-driven",
        description_template=(
            "El contexto {scope} se activó {occurrences} veces en la ventana "
            "de {window_days} días (intervalo mediano ~{median_interval} días). "
            "Regularidad detectada."
        ),
    ),
    PatternDefinition(
        pattern_id="context_recurrence_resource_pressure_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        domain="resources",
        scope_mental_models=frozenset({"resource_pressure"}),
        min_occurrences=3,
        strength_threshold=0.6,
        frequency_label="daily",
        description_template=(
            "El contexto {scope} se activó {occurrences} veces en la ventana "
            "de {window_days} días (intervalo mediano ~{median_interval} días). "
            "Regularidad detectada."
        ),
    ),
    PatternDefinition(
        pattern_id="context_recurrence_auth_compromise_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        domain="security",
        scope_mental_models=frozenset({"auth_compromise"}),
        min_occurrences=2,
        strength_threshold=0.6,
        frequency_label="event-driven",
        description_template=(
            "El contexto {scope} se activó {occurrences} veces en la ventana "
            "de {window_days} días (intervalo mediano ~{median_interval} días). "
            "Regularidad detectada."
        ),
    ),
    PatternDefinition(
        pattern_id="context_recurrence_connectivity_degradation_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        domain="network",
        scope_mental_models=frozenset({"connectivity_degradation"}),
        min_occurrences=3,
        strength_threshold=0.6,
        frequency_label="daily",
        description_template=(
            "El contexto {scope} se activó {occurrences} veces en la ventana "
            "de {window_days} días (intervalo mediano ~{median_interval} días). "
            "Regularidad detectada."
        ),
    ),
)

PATTERN_DEFINITIONS: dict[str, PatternDefinition] = {
    definition.pattern_id: definition for definition in PATTERN_LIBRARY
}
