"""Tolerance Library - declarative deviation tolerances (Reasoning/Detect Deviation).

The Tolerance Library is procedural memory (P3): explicit, auditable and
purpose-dependent thresholds that declare WHAT counts as a deviation for a
known pattern. It never detects anything by itself - the detector in
``anomaly-service`` does the measurement. Tolerances are declarative knowledge,
never reasoning.

Per the framework concept, tolerance thresholds must be explicit, auditable and
purpose-dependent, and anomaly detection is always RELATIVE to an expected
pattern - a tolerance only makes sense paired with a PatternDefinition in the
Pattern Library. Each entry below maps one-to-one to a ``context_recurrence_*_v1``
PatternDefinition of Sprint 5.

Deviation schemes (the exact measurement, documented and unit-tested):

* ``days_off_schedule`` - for patterns with a measured cadence (hourly/daily/
  weekly): the Active Context is compared against the expected next activation
  of the pattern. ``expected_interval_days`` is derived from the pattern's
  measured ``frequency`` label via ``FREQUENCY_INTERVAL_DAYS``.
  ``deviation_score = abs(observed_gap_days - expected_interval) / expected_interval``
  where ``observed_gap_days = (active.activated_at - pattern.detected_at)``.
  A value of 0 means the context is exactly on schedule; 1.0 means one full
  expected interval off.

* ``count_exceeding_window`` - for event-driven patterns (no cadence): counts
  the activations of the same scope inside a short recent window
  ``[active.activated_at - window_days, active.activated_at]`` (the Active
  Context included). ``deviation_score = count / max(expected_max_activations, 1)``.
  A value of 1.0 means the scope activated exactly the expected maximum; >1.0
  means it clustered beyond expectation.

An anomaly is emitted only when ``deviation_score > threshold``. The threshold
is a ratio on the same scale as the score, explicit and auditable.
"""
from dataclasses import dataclass, field

from libs.procedural_memory.pattern_library import (
    PATTERN_TYPE_TEMPORAL,
    PATTERN_TYPES,
)
from libs.reasoning.anomaly import ANOMALY_CLASS_POINT, ANOMALY_CLASSES

# Deviation measurement schemes implemented by the detector.
DEVIATION_SPEC_DAYS_OFF_SCHEDULE = "days_off_schedule"
DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW = "count_exceeding_window"
DEVIATION_SPECS: frozenset[str] = frozenset(
    {
        DEVIATION_SPEC_DAYS_OFF_SCHEDULE,
        DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW,
    }
)

# Measured frequency label -> expected cadence in days (procedural knowledge).
# ``event-driven`` has no cadence and is NOT listed: it pairs only with
# ``count_exceeding_window`` tolerances.
FREQUENCY_INTERVAL_DAYS: dict[str, float] = {
    "hourly": 1 / 24,
    "daily": 1.0,
    "weekly": 7.0,
}


@dataclass(frozen=True)
class ToleranceDefinition:
    """Declarative deviation tolerance for a known pattern (procedural memory).

    ``tolerance_id`` is versioned (``_v1``/``_v2``): revising a tolerance means
    publishing a NEW version, never mutating a published one. ``threshold`` is
    the ratio a ``deviation_score`` must exceed to emit an anomaly.
    """

    tolerance_id: str
    pattern_type: str = PATTERN_TYPE_TEMPORAL
    scope_mental_models: frozenset[str] = field(default_factory=frozenset)
    scope_purposes: frozenset[str] = field(default_factory=frozenset)
    anomaly_class: str = ANOMALY_CLASS_POINT
    deviation_spec: str = DEVIATION_SPEC_DAYS_OFF_SCHEDULE
    threshold: float = 0.5
    expected_max_activations: int = 1
    window_days: float = 1.0

    def __post_init__(self) -> None:
        if self.pattern_type not in PATTERN_TYPES:
            raise ValueError(f"unknown pattern_type: {self.pattern_type}")  # noqa: TRY003
        if self.anomaly_class not in ANOMALY_CLASSES:
            raise ValueError(f"unknown anomaly_class: {self.anomaly_class}")  # noqa: TRY003
        if self.deviation_spec not in DEVIATION_SPECS:
            raise ValueError(f"unknown deviation_spec: {self.deviation_spec}")  # noqa: TRY003
        if self.threshold < 0:
            raise ValueError("threshold must be >= 0")  # noqa: TRY003
        if self.deviation_spec == DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW:
            if self.expected_max_activations < 1:
                raise ValueError("expected_max_activations must be >= 1")  # noqa: TRY003
            if self.window_days <= 0:
                raise ValueError("window_days must be > 0")  # noqa: TRY003


TOLERANCE_LIBRARY: tuple[ToleranceDefinition, ...] = (
    ToleranceDefinition(
        tolerance_id="schedule_deviation_capacity_risk_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        scope_mental_models=frozenset({"capacity_risk"}),
        anomaly_class=ANOMALY_CLASS_POINT,
        deviation_spec=DEVIATION_SPEC_DAYS_OFF_SCHEDULE,
        threshold=0.5,
    ),
    ToleranceDefinition(
        tolerance_id="clustering_deviation_service_failure_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        scope_mental_models=frozenset({"service_failure"}),
        anomaly_class=ANOMALY_CLASS_POINT,
        deviation_spec=DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW,
        threshold=1.0,
        expected_max_activations=1,
        window_days=1.0,
    ),
    ToleranceDefinition(
        tolerance_id="schedule_deviation_resource_pressure_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        scope_mental_models=frozenset({"resource_pressure"}),
        anomaly_class=ANOMALY_CLASS_POINT,
        deviation_spec=DEVIATION_SPEC_DAYS_OFF_SCHEDULE,
        threshold=0.5,
    ),
    ToleranceDefinition(
        tolerance_id="clustering_deviation_auth_compromise_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        scope_mental_models=frozenset({"auth_compromise"}),
        anomaly_class=ANOMALY_CLASS_POINT,
        deviation_spec=DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW,
        threshold=1.0,
        expected_max_activations=2,
        window_days=1.0,
    ),
    ToleranceDefinition(
        tolerance_id="schedule_deviation_connectivity_degradation_v1",
        pattern_type=PATTERN_TYPE_TEMPORAL,
        scope_mental_models=frozenset({"connectivity_degradation"}),
        anomaly_class=ANOMALY_CLASS_POINT,
        deviation_spec=DEVIATION_SPEC_DAYS_OFF_SCHEDULE,
        threshold=0.5,
    ),
)

TOLERANCE_DEFINITIONS: dict[str, ToleranceDefinition] = {
    definition.tolerance_id: definition for definition in TOLERANCE_LIBRARY
}