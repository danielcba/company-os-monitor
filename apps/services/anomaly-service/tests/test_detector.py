"""Unit tests for the Anomaly Detector (Reasoning/Detect Deviation) and Tolerance Library.

Synthetic Context/Pattern streams only - no database. Covers: one
positive/negative case per tolerance, deviation_score with known values, the
anti-invention constraint on the factual rationale, the "relative to patterns,
never absolute" rule (no pattern -> no anomaly), scope resolution through the
anchor context, most-recent pattern selection, idempotence and tenant
filtering.
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from libs.perception.context import Context
from libs.procedural_memory.tolerance_library import (
    DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW,
    TOLERANCE_LIBRARY,
    ToleranceDefinition,
)
from libs.reasoning.pattern import PatternCreate, build_pattern

from src.detector import detect

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

# Words that would violate the Anomaly boundary: the signal must never
# explain (cause) or predict (Hypothesis territory).
BANNED_ANOMALY_LANGUAGE = (
    "porque",
    "fallará",
    "va a fallar",
    "causa",
    "causado",
    "predice",
    "predicción",
    "provoca",
    "explica",
    "debería",
    "comprometido",
)


def make_context(
    model_id: str,
    purpose: str,
    activated_at: datetime,
    *,
    is_active: bool,
    tenant_id: uuid.UUID = TENANT,
) -> Context:
    return Context(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        evidence_ids=[uuid.uuid4()],
        mental_model_id=model_id,
        purpose=purpose,
        coherence_score=0.7,
        competing_models=[],
        activated_at=activated_at,
        is_active=is_active,
    )


def make_pattern(
    anchor: Context,
    frequency: str,
    detected_at: datetime,
    *,
    library_pattern_id: str = "probe_v1",
    pattern_type: str = "temporal",
):
    return build_pattern(
        PatternCreate(
            tenant_id=anchor.tenant_id,
            context_id=anchor.id,
            pattern_type=pattern_type,
            description="factual description",
            strength_measure=1.0,
            frequency=frequency,
            library_pattern_id=library_pattern_id,
            detected_at=detected_at,
        )
    )


def weekly_pattern(anchor: Context, detected_at: datetime):
    return make_pattern(anchor, "weekly", detected_at)


def event_pattern(anchor: Context, detected_at: datetime):
    return make_pattern(anchor, "event-driven", detected_at)


def tolerance_frequency(tolerance: ToleranceDefinition) -> str:
    if tolerance.deviation_spec == DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW:
        return "event-driven"
    return "weekly"


@pytest.mark.parametrize("tolerance", TOLERANCE_LIBRARY)
def test_each_tolerance_detects_a_deviating_context(tolerance):
    """One positive per tolerance: an Active Context that deviates -> anomaly."""
    scope = min(tolerance.scope_mental_models)
    purpose = "infrastructure_health"
    anchor = make_context(scope, purpose, NOW - timedelta(days=7), is_active=False)
    pattern = make_pattern(anchor, tolerance_frequency(tolerance), NOW - timedelta(days=7))

    if tolerance.deviation_spec == DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW:
        extras = [
            make_context(scope, purpose, NOW - timedelta(hours=6), is_active=False),
            make_context(scope, purpose, NOW - timedelta(hours=3), is_active=False),
        ]
        active = make_context(scope, purpose, NOW, is_active=True)
        stream = [anchor, *extras, active]
    else:
        active = make_context(scope, purpose, NOW + timedelta(days=14), is_active=True)
        stream = [anchor, active]

    result = detect(stream, [pattern], [tolerance], tenant_id=TENANT)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.context_id == active.id
    assert candidate.pattern_id == pattern.id
    assert candidate.mental_model_id == scope
    assert candidate.purpose == purpose
    assert candidate.deviation_score > candidate.tolerance_threshold
    assert candidate.tolerance_id == tolerance.tolerance_id
    assert candidate.deviation_spec == tolerance.deviation_spec
    assert candidate.anomaly_class == "point"
    assert result.contexts_without_pattern == 0
    assert result.contexts_without_tolerance == 0


@pytest.mark.parametrize("tolerance", TOLERANCE_LIBRARY)
def test_context_within_pattern_is_not_anomalous(tolerance):
    """Negative: an Active Context inside the expected pattern -> no anomaly."""
    scope = min(tolerance.scope_mental_models)
    purpose = "infrastructure_health"
    anchor = make_context(scope, purpose, NOW - timedelta(days=7), is_active=False)
    pattern = make_pattern(anchor, tolerance_frequency(tolerance), NOW - timedelta(days=7))
    active = make_context(scope, purpose, NOW, is_active=True)

    result = detect([anchor, active], [pattern], [tolerance], tenant_id=TENANT)
    assert result.candidates == []
    assert result.active_contexts == 1
    assert result.contexts_without_pattern == 0
    assert result.contexts_without_tolerance == 0


@pytest.mark.parametrize("tolerance", TOLERANCE_LIBRARY)
def test_context_without_expected_pattern_is_never_anomalous(tolerance):
    """No expected Pattern -> no deviation (relative to patterns, never absolute)."""
    scope = min(tolerance.scope_mental_models)
    active = make_context(scope, "infrastructure_health", NOW, is_active=True)

    result = detect([active], [], [tolerance], tenant_id=TENANT)
    assert result.candidates == []
    assert result.contexts_without_pattern == 1
    assert result.active_contexts == 1


def test_deviation_score_with_known_values():
    anchor = make_context("capacity_risk", "infrastructure_health", NOW - timedelta(days=7), is_active=False)
    pattern = weekly_pattern(anchor, NOW - timedelta(days=7))
    tolerance = TOLERANCE_LIBRARY[0]

    on_schedule = make_context("capacity_risk", "infrastructure_health", NOW, is_active=True)
    assert detect([anchor, on_schedule], [pattern], [tolerance], tenant_id=TENANT).candidates == []

    one_interval_late = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=7), is_active=True
    )
    candidate = detect(
        [anchor, one_interval_late], [pattern], [tolerance], tenant_id=TENANT
    ).candidates[0]
    assert candidate.deviation_score == pytest.approx(1.0)

    two_intervals_late = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=14), is_active=True
    )
    candidate = detect(
        [anchor, two_intervals_late], [pattern], [tolerance], tenant_id=TENANT
    ).candidates[0]
    assert candidate.deviation_score == pytest.approx(2.0)


def test_count_exceeding_window_with_known_values():
    anchor = make_context("service_failure", "security_posture", NOW - timedelta(days=3), is_active=False)
    pattern = event_pattern(anchor, NOW - timedelta(days=3))
    tolerance = next(
        t
        for t in TOLERANCE_LIBRARY
        if t.deviation_spec == DEVIATION_SPEC_COUNT_EXCEEDING_WINDOW
        and "service_failure" in t.scope_mental_models
    )
    assert tolerance.expected_max_activations == 1

    single = make_context("service_failure", "security_posture", NOW, is_active=True)
    assert detect([anchor, single], [pattern], [tolerance], tenant_id=TENANT).candidates == []

    clustered = [
        make_context("service_failure", "security_posture", NOW - timedelta(hours=6), is_active=False),
        make_context("service_failure", "security_posture", NOW - timedelta(hours=2), is_active=False),
        make_context("service_failure", "security_posture", NOW, is_active=True),
    ]
    candidate = detect([anchor, *clustered], [pattern], [tolerance], tenant_id=TENANT).candidates[0]
    assert candidate.deviation_score == pytest.approx(3.0)
    assert candidate.pattern_id == pattern.id


def test_context_without_tolerance_is_never_anomalous():
    anchor = make_context("capacity_risk", "infrastructure_health", NOW - timedelta(days=7), is_active=False)
    pattern = weekly_pattern(anchor, NOW - timedelta(days=7))
    active = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=14), is_active=True
    )
    result = detect([anchor, active], [pattern], [], tenant_id=TENANT)
    assert result.candidates == []
    assert result.contexts_without_tolerance == 1
    assert result.contexts_without_pattern == 0


def test_event_driven_pattern_with_schedule_tolerance_has_no_applicable_measure():
    anchor = make_context("capacity_risk", "infrastructure_health", NOW - timedelta(days=7), is_active=False)
    pattern = event_pattern(anchor, NOW - timedelta(days=7))
    active = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=14), is_active=True
    )
    tolerance = TOLERANCE_LIBRARY[0]  # days_off_schedule over a schedule-less pattern
    result = detect([anchor, active], [pattern], [tolerance], tenant_id=TENANT)
    assert result.candidates == []
    assert result.contexts_without_tolerance == 1


def test_rationale_is_factual_never_causal_or_predictive():
    anchor = make_context("capacity_risk", "infrastructure_health", NOW - timedelta(days=7), is_active=False)
    pattern = weekly_pattern(anchor, NOW - timedelta(days=7))
    active = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=14), is_active=True
    )
    candidate = detect(
        [anchor, active], [pattern], [TOLERANCE_LIBRARY[0]], tenant_id=TENANT
    ).candidates[0]
    lowered = candidate.rationale.lower()
    for banned in BANNED_ANOMALY_LANGUAGE:
        assert banned not in lowered
    assert "desviación" in lowered


def test_expected_pattern_is_the_most_recent_for_the_scope():
    older_anchor = make_context(
        "capacity_risk", "infrastructure_health", NOW - timedelta(days=20), is_active=False
    )
    newer_anchor = make_context(
        "capacity_risk", "infrastructure_health", NOW - timedelta(days=7), is_active=False
    )
    old = weekly_pattern(older_anchor, NOW - timedelta(days=20))
    new = weekly_pattern(newer_anchor, NOW - timedelta(days=7))
    active = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=7), is_active=True
    )
    result = detect(
        [older_anchor, newer_anchor, active], [new, old], [TOLERANCE_LIBRARY[0]], tenant_id=TENANT
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].pattern_id == new.id


def test_pattern_is_matched_by_anchor_scope_not_active_scope():
    anchor = make_context("capacity_risk", "infrastructure_health", NOW - timedelta(days=7), is_active=False)
    pattern = weekly_pattern(anchor, NOW - timedelta(days=7))
    active = make_context("service_failure", "security_posture", NOW, is_active=True)
    result = detect([anchor, active], [pattern], TOLERANCE_LIBRARY, tenant_id=TENANT)
    assert result.candidates == []
    assert result.contexts_without_pattern == 1


def test_explicit_active_contexts_subset_is_used():
    anchor = make_context("capacity_risk", "infrastructure_health", NOW - timedelta(days=7), is_active=False)
    pattern = weekly_pattern(anchor, NOW - timedelta(days=7))
    active = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=14), is_active=True
    )
    stale = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=14), is_active=False
    )
    result = detect(
        [anchor, active, stale],
        [pattern],
        [TOLERANCE_LIBRARY[0]],
        active_contexts=[active],
        tenant_id=TENANT,
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].context_id == active.id
    assert result.active_contexts == 1


def test_detection_is_deterministic_and_idempotent():
    anchor = make_context("capacity_risk", "infrastructure_health", NOW - timedelta(days=7), is_active=False)
    pattern = weekly_pattern(anchor, NOW - timedelta(days=7))
    active = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=14), is_active=True
    )
    stream = [anchor, active]
    first = detect(stream, [pattern], TOLERANCE_LIBRARY, tenant_id=TENANT)
    second = detect(stream, [pattern], TOLERANCE_LIBRARY, tenant_id=TENANT)
    assert first.candidates == second.candidates
    assert first.active_contexts == second.active_contexts
    assert first.contexts_without_pattern == second.contexts_without_pattern
    assert first.contexts_without_tolerance == second.contexts_without_tolerance


def test_detect_filters_by_tenant():
    anchor_a = make_context("capacity_risk", "infrastructure_health", NOW - timedelta(days=7), is_active=False)
    pattern_a = weekly_pattern(anchor_a, NOW - timedelta(days=7))
    active_a = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=14), is_active=True
    )
    active_b = make_context(
        "capacity_risk", "infrastructure_health", NOW + timedelta(days=14),
        is_active=True, tenant_id=OTHER_TENANT,
    )
    stream = [anchor_a, active_a, active_b]
    result = detect(stream, [pattern_a], TOLERANCE_LIBRARY, tenant_id=TENANT)
    assert len(result.candidates) == 1
    assert result.candidates[0].context_id == active_a.id
    assert result.active_contexts == 1