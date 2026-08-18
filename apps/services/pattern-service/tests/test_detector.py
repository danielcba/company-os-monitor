"""Unit tests for the Pattern Detector (Reasoning/Generalize) and the Pattern Library.

Synthetic Context streams only - no database. Covers: one positive/negative
case per PatternDefinition, the strength_measure scoring scheme with known
values, the frequency_label derivation, the anti-invention constraint on the
factual description, window filtering, below-threshold metrics and the
deterministic/idempotent pattern id.
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from libs.perception.context import Context
from libs.procedural_memory.pattern_library import (
    FREQUENCY_LABELS,
    PATTERN_LIBRARY,
    PATTERN_TYPE_TEMPORAL,
    PatternDefinition,
)
from libs.reasoning.pattern import (
    PatternCreate,
    build_pattern,
    pattern_id,
)

from src.detector import derive_frequency, detect

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)

# Words that would violate P4 (patterns reveal regularity; never cause/predict).
BANNED_PATTERN_LANGUAGE = (
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
)


def make_context(
    model_id: str,
    purpose: str,
    activated_at: datetime,
    ctx_id: uuid.UUID | None = None,
) -> Context:
    return Context(
        id=ctx_id or uuid.uuid4(),
        tenant_id=TENANT,
        evidence_ids=[uuid.uuid4()],
        mental_model_id=model_id,
        purpose=purpose,
        coherence_score=0.7,
        competing_models=[],
        activated_at=activated_at,
    )


def spaced_activations(
    model_id: str,
    purpose: str,
    count: int,
    spacing: timedelta,
    end: datetime = NOW,
) -> list[Context]:
    """Activations in ascending time ending at ``end``, spaced by ``spacing``."""
    return [
        make_context(model_id, purpose, end - spacing * (count - 1 - i))
        for i in range(count)
    ]


@pytest.mark.parametrize("definition", PATTERN_LIBRARY)
def test_each_definition_detects_sufficient_support(definition):
    model = min(definition.scope_mental_models)
    purpose = min(definition.scope_purposes, default="infrastructure_health")
    contexts = spaced_activations(
        model, purpose, definition.min_occurrences, timedelta(days=7)
    )
    result = detect(contexts, [definition], window_days=28, now=NOW)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.library_pattern_id == definition.pattern_id
    assert candidate.pattern_type == definition.pattern_type
    assert candidate.mental_model_id == model
    assert candidate.purpose == purpose
    assert candidate.occurrences == definition.min_occurrences
    assert candidate.strength_measure == pytest.approx(1.0)
    assert candidate.frequency in FREQUENCY_LABELS
    assert candidate.context_id == contexts[-1].id
    assert str(definition.min_occurrences) in candidate.description
    assert model in candidate.description


@pytest.mark.parametrize("definition", PATTERN_LIBRARY)
def test_insufficient_support_is_not_detected(definition):
    model = min(definition.scope_mental_models)
    purpose = min(definition.scope_purposes, default="infrastructure_health")
    contexts = spaced_activations(model, purpose, 1, timedelta(days=7))
    result = detect(contexts, [definition], window_days=28, now=NOW)
    assert result.candidates == []
    assert result.evaluated == 1
    assert result.below_threshold == 1


@pytest.mark.parametrize("definition", PATTERN_LIBRARY)
def test_absent_scope_is_not_evaluated(definition):
    foreign = "capacity_risk" if "capacity_risk" not in definition.scope_mental_models else "service_failure"
    contexts = spaced_activations(foreign, "infrastructure_health", 3, timedelta(days=7))
    result = detect(contexts, [definition], window_days=28, now=NOW)
    assert result.candidates == []
    assert result.evaluated == 0
    assert result.below_threshold == 0


def test_strength_scoring_with_known_values():
    definition = PatternDefinition(
        pattern_id="scoring_probe_v1",
        scope_mental_models=frozenset({"capacity_risk"}),
        min_occurrences=3,
        strength_threshold=0.6,
    )
    two = spaced_activations("capacity_risk", "infrastructure_health", 2, timedelta(days=7))
    assert detect(two, [definition], window_days=28, now=NOW).candidates[0].strength_measure == pytest.approx(0.6667, abs=1e-4)

    three = spaced_activations("capacity_risk", "infrastructure_health", 3, timedelta(days=7))
    assert detect(three, [definition], window_days=28, now=NOW).candidates[0].strength_measure == pytest.approx(1.0)

    five = spaced_activations("capacity_risk", "infrastructure_health", 5, timedelta(days=7))
    assert detect(five, [definition], window_days=28, now=NOW).candidates[0].strength_measure == pytest.approx(1.0)


def test_threshold_gates_partial_support():
    definition = PatternDefinition(
        pattern_id="threshold_probe_v1",
        scope_mental_models=frozenset({"capacity_risk"}),
        min_occurrences=3,
        strength_threshold=0.8,
    )
    two = spaced_activations("capacity_risk", "infrastructure_health", 2, timedelta(days=7))
    result = detect(two, [definition], window_days=28, now=NOW)
    assert result.candidates == []
    assert result.below_threshold == 1
    assert result.evaluated == 1


@pytest.mark.parametrize(
    "spacing,expected",
    [
        (timedelta(minutes=30), "hourly"),
        (timedelta(hours=12), "daily"),
        (timedelta(days=1), "daily"),
        (timedelta(days=2), "weekly"),
        (timedelta(days=7), "weekly"),
        (timedelta(days=30), "event-driven"),
    ],
)
def test_frequency_label_derivation(spacing, expected):
    contexts = spaced_activations("capacity_risk", "infrastructure_health", 3, spacing)
    median_days, frequency = derive_frequency(contexts)
    assert frequency == expected
    assert median_days is not None
    assert median_days == pytest.approx(spacing.total_seconds() / 86400.0)


def test_frequency_falls_back_to_event_driven_with_single_activation():
    contexts = spaced_activations("capacity_risk", "infrastructure_health", 1, timedelta(days=1))
    median_days, frequency = derive_frequency(contexts)
    assert median_days is None
    assert frequency == "event-driven"


def test_frequency_label_derived_from_measured_interval_not_declaration():
    definition = PatternDefinition(
        pattern_id="freq_probe_v1",
        scope_mental_models=frozenset({"capacity_risk"}),
        min_occurrences=3,
        strength_threshold=0.6,
        frequency_label="weekly",
    )
    daily = spaced_activations("capacity_risk", "infrastructure_health", 3, timedelta(days=1))
    candidate = detect(daily, [definition], window_days=28, now=NOW).candidates[0]
    assert candidate.frequency == "daily"


@pytest.mark.parametrize("definition", PATTERN_LIBRARY)
def test_description_is_factual_never_causal_or_predictive(definition):
    model = min(definition.scope_mental_models)
    purpose = min(definition.scope_purposes, default="infrastructure_health")
    contexts = spaced_activations(
        model, purpose, definition.min_occurrences, timedelta(days=7)
    )
    candidate = detect(contexts, [definition], window_days=28, now=NOW).candidates[0]
    lowered = candidate.description.lower()
    for banned in BANNED_PATTERN_LANGUAGE:
        assert banned not in lowered
    assert "regularidad" in lowered


def test_window_excludes_activations_older_than_window_days():
    definition = PatternDefinition(
        pattern_id="window_probe_v1",
        scope_mental_models=frozenset({"capacity_risk"}),
        min_occurrences=3,
        strength_threshold=0.6,
    )
    inside = spaced_activations("capacity_risk", "infrastructure_health", 2, timedelta(days=7))
    stale = make_context("capacity_risk", "infrastructure_health", NOW - timedelta(days=40))
    result = detect([*inside, stale], [definition], window_days=28, now=NOW)
    assert result.candidates[0].occurrences == 2
    assert result.candidates[0].strength_measure == pytest.approx(2 / 3, abs=1e-4)


def test_purpose_scope_filters_groups():
    definition = PatternDefinition(
        pattern_id="purpose_probe_v1",
        scope_mental_models=frozenset({"capacity_risk"}),
        scope_purposes=frozenset({"infrastructure_health"}),
        min_occurrences=2,
        strength_threshold=0.6,
    )
    health = spaced_activations("capacity_risk", "infrastructure_health", 2, timedelta(days=7))
    capacity = spaced_activations("capacity_risk", "capacity_management", 3, timedelta(days=7))
    result = detect([*health, *capacity], [definition], window_days=28, now=NOW)
    assert len(result.candidates) == 1
    assert result.candidates[0].purpose == "infrastructure_health"


def test_below_threshold_and_passing_counts():
    weak = PatternDefinition(
        pattern_id="weak_probe_v1",
        scope_mental_models=frozenset({"capacity_risk"}),
        min_occurrences=4,
        strength_threshold=0.6,
    )
    strong = PatternDefinition(
        pattern_id="strong_probe_v1",
        scope_mental_models=frozenset({"service_failure"}),
        min_occurrences=2,
        strength_threshold=0.6,
    )
    contexts = [
        *spaced_activations("capacity_risk", "infrastructure_health", 2, timedelta(days=7)),
        *spaced_activations("service_failure", "security_posture", 3, timedelta(days=7)),
    ]
    result = detect(contexts, [weak, strong], window_days=28, now=NOW)
    assert len(result.candidates) == 1
    assert result.candidates[0].library_pattern_id == "strong_probe_v1"
    assert result.evaluated == 2
    assert result.below_threshold == 1


def test_detection_is_deterministic_and_idempotent():
    contexts = spaced_activations("capacity_risk", "infrastructure_health", 3, timedelta(days=7))
    first = detect(contexts, [PATTERN_LIBRARY[0]], window_days=28, now=NOW)
    second = detect(contexts, [PATTERN_LIBRARY[0]], window_days=28, now=NOW)
    assert first.candidates == second.candidates
    assert first.evaluated == second.evaluated
    assert first.below_threshold == second.below_threshold


def test_pattern_id_is_deterministic_and_library_version_traceable():
    ctx_id = uuid.uuid4()
    v1 = pattern_id(TENANT, ctx_id, "context_recurrence_capacity_risk_v1")
    assert v1 == pattern_id(TENANT, ctx_id, "context_recurrence_capacity_risk_v1")
    v2 = pattern_id(TENANT, ctx_id, "context_recurrence_capacity_risk_v2")
    assert v1 != v2
    other_context = pattern_id(TENANT, uuid.uuid4(), "context_recurrence_capacity_risk_v1")
    assert v1 != other_context
    other_tenant = pattern_id(uuid.uuid4(), ctx_id, "context_recurrence_capacity_risk_v1")
    assert v1 != other_tenant


def test_build_pattern_produces_same_id_for_same_facts():
    ctx_id = uuid.uuid4()
    facts = {
        "tenant_id": TENANT,
        "context_id": ctx_id,
        "pattern_type": PATTERN_TYPE_TEMPORAL,
        "description": "El contexto capacity_risk para infrastructure_health se activó 3 veces en la ventana de 28 días (intervalo mediano ~7.0 días). Regularidad detectada.",
        "strength_measure": 1.0,
        "frequency": "weekly",
        "library_pattern_id": "context_recurrence_capacity_risk_v1",
    }
    first = build_pattern(PatternCreate(**facts))
    second = build_pattern(PatternCreate(**facts))
    assert first.id == second.id
    assert first.tenant_id == TENANT
    assert first.context_id == ctx_id
    assert first.strength_measure == 1.0
    assert first.frequency == "weekly"
