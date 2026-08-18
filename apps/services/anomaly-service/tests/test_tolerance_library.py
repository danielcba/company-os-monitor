"""Unit tests for the Tolerance Library (procedural memory, declarative only).

Covers: catalog coverage of the 5 PatternDefinitions of Sprint 5, the
frequency -> expected interval mapping, validation rules and versioned
tolerance ids.
"""
import pytest
from libs.procedural_memory.pattern_library import (
    PATTERN_LIBRARY,
    PATTERN_TYPE_TEMPORAL,
)
from libs.procedural_memory.tolerance_library import (
    DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW,
    DEVIATION_SPEC_DAYS_OFF_SCHEDULE,
    FREQUENCY_INTERVAL_DAYS,
    TOLERANCE_DEFINITIONS,
    TOLERANCE_LIBRARY,
    ToleranceDefinition,
)
from libs.reasoning.anomaly import (
    ANOMALY_CLASS_CONTEXTUAL,
    ANOMALY_CLASS_POINT,
)


def test_catalog_covers_every_pattern_definition_scope():
    pattern_scopes = {
        min(definition.scope_mental_models) for definition in PATTERN_LIBRARY
    }
    tolerance_scopes = {
        min(definition.scope_mental_models) for definition in TOLERANCE_LIBRARY
    }
    assert tolerance_scopes == pattern_scopes
    assert len(TOLERANCE_LIBRARY) == len(PATTERN_LIBRARY) == 5


def test_every_tolerance_maps_to_a_point_temporal_deviation():
    for tolerance in TOLERANCE_LIBRARY:
        assert tolerance.pattern_type == PATTERN_TYPE_TEMPORAL
        assert tolerance.anomaly_class == ANOMALY_CLASS_POINT
        assert tolerance.deviation_spec in {
            DEVIATION_SPEC_DAYS_OFF_SCHEDULE,
            DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW,
        }
        assert tolerance.threshold >= 0
        assert tolerance.tolerance_id in TOLERANCE_DEFINITIONS


def test_schedule_tolerances_pair_with_scheduled_pattern_definitions():
    for tolerance in TOLERANCE_LIBRARY:
        if tolerance.deviation_spec != DEVIATION_SPEC_DAYS_OFF_SCHEDULE:
            continue
        pattern = next(
            definition
            for definition in PATTERN_LIBRARY
            if definition.scope_mental_models == tolerance.scope_mental_models
        )
        assert pattern.frequency_label in FREQUENCY_INTERVAL_DAYS


def test_frequency_interval_mapping_known_values():
    assert FREQUENCY_INTERVAL_DAYS["hourly"] == pytest.approx(1 / 24)
    assert FREQUENCY_INTERVAL_DAYS["daily"] == pytest.approx(1.0)
    assert FREQUENCY_INTERVAL_DAYS["weekly"] == pytest.approx(7.0)
    assert "event-driven" not in FREQUENCY_INTERVAL_DAYS


def test_tolerance_ids_are_versioned():
    for tolerance in TOLERANCE_LIBRARY:
        assert tolerance.tolerance_id.endswith("_v1")
        assert "_v1" in tolerance.tolerance_id


def test_revision_publishes_a_new_version_never_mutates():
    v1 = TOLERANCE_DEFINITIONS["schedule_deviation_capacity_risk_v1"]
    v2 = ToleranceDefinition(
        tolerance_id="schedule_deviation_capacity_risk_v2",
        scope_mental_models=frozenset({"capacity_risk"}),
        threshold=0.7,
    )
    assert v1.tolerance_id != v2.tolerance_id
    assert v1.threshold == 0.5
    assert v2.threshold == 0.7


@pytest.mark.parametrize(
    "kwargs",
    [
        {"anomaly_class": "novel_class"},
        {"deviation_spec": "novel_spec"},
        {"threshold": -0.1},
        {"pattern_type": "novel_type"},
    ],
)
def test_validation_rejects_invalid_definitions(kwargs):
    with pytest.raises(ValueError):
        ToleranceDefinition(
            tolerance_id="invalid_probe_v1",
            scope_mental_models=frozenset({"capacity_risk"}),
            **kwargs,
        )


def test_count_exceeding_window_requires_positive_window():
    with pytest.raises(ValueError):
        ToleranceDefinition(
            tolerance_id="bad_window_v1",
            deviation_spec=DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW,
            window_days=0,
        )
    with pytest.raises(ValueError):
        ToleranceDefinition(
            tolerance_id="bad_max_v1",
            deviation_spec=DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW,
            expected_max_activations=0,
        )


def test_reserved_classes_are_not_implemented():
    for tolerance in TOLERANCE_LIBRARY:
        assert tolerance.anomaly_class != ANOMALY_CLASS_CONTEXTUAL


def test_tolerances_from_env_keeps_defaults_without_overrides(monkeypatch):
    from src.main import tolerances_from_env

    for env_name in (
        "TOLERANCE_SCHEDULE_DEVIATION_CAPACITY_RISK_THRESHOLD",
        "TOLERANCE_CLUSTERING_DEVIATION_SERVICE_FAILURE_THRESHOLD",
    ):
        monkeypatch.delenv(env_name, raising=False)
    loaded = tolerances_from_env()
    assert loaded == TOLERANCE_LIBRARY
    assert {t.tolerance_id: t.threshold for t in loaded} == {
        t.tolerance_id: t.threshold for t in TOLERANCE_LIBRARY
    }


def test_tolerances_from_env_applies_documented_override(monkeypatch):
    from src.main import tolerances_from_env

    monkeypatch.setenv(
        "TOLERANCE_SCHEDULE_DEVIATION_CAPACITY_RISK_THRESHOLD", "0.8"
    )
    loaded = tolerances_from_env()
    thresholds = {t.tolerance_id: t.threshold for t in loaded}
    assert thresholds["schedule_deviation_capacity_risk_v1"] == pytest.approx(0.8)
    # Unoverridden tolerances keep their canonical defaults.
    assert thresholds["clustering_deviation_service_failure_v1"] == pytest.approx(1.0)