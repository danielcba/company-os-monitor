"""Hypothesis Generator - Reasoning/Predict capability (pure functions, no I/O).

Input: an Anomaly + the tenant's Context stream + its Patterns + the
Hypothesis Template Library. Transform: instantiate the candidate explanation
templates whose scope matches the anomaly's scope and emit one
``HypothesisCreate`` per template. Output: multiple competing candidate
Hypotheses (>=2 when templates apply - premature convergence on a single
explanation is a cognitive failure per the framework).

The generator NEVER reasons by itself: templates are declarative procedural
memory and facts are measured, never invented. It NEVER confirms or falsifies
(status stays ``candidate``; that requires future evidence + Confidence,
Sprint 8). It NEVER explains on its own beyond the template text - causal or
predictive language beyond the declared templates is out of scope.

Placeholders instantiated with measured facts:
  ``{scope}``            - ``{mental_model} para {purpose}`` of the anomaly
  ``{anomaly_class}``    - anomaly class (``point`` in the MVP)
  ``{deviation_score}``  - quantified deviation of the anomaly
  ``{frequency}``        - expected pattern's measured frequency (if known)

``coherence_score`` is the template's declarative ``coherence_estimate`` - a
documented prior per explanation, NOT a calibrated measurement. Calibrated
coherence (S + C + ECE) is computed by Confidence (Sprint 8) and out of scope.
"""
from collections.abc import Sequence

from libs.perception.context import Context
from libs.procedural_memory.hypothesis_templates import (
    HYPOTHESIS_TEMPLATE_LIBRARY,
    HypothesisTemplate,
)
from libs.reasoning.anomaly import Anomaly
from libs.reasoning.hypothesis import STATUS_CANDIDATE, HypothesisCreate
from libs.reasoning.pattern import Pattern


def _anomaly_scope(
    anomaly: Anomaly, contexts: Sequence[Context]
) -> tuple[str, str] | None:
    """Resolve ``(mental_model_id, purpose)`` through the anomaly's Active Context.

    The ``anomalies`` row stores ``context_id`` (the Active Context that
    deviated) but not its scope; the scope is recovered through ``contexts``.
    """
    for ctx in contexts:
        if ctx.id == anomaly.context_id:
            return ctx.mental_model_id, ctx.purpose
    return None


def resolve_anomaly_scope(
    anomaly: Anomaly, contexts: Sequence[Context]
) -> tuple[str, str] | None:
    """Public scope resolution (used by the service for tenant-scoped metrics)."""
    return _anomaly_scope(anomaly, contexts)


def _expected_pattern(
    anomaly: Anomaly, patterns: Sequence[Pattern]
) -> Pattern | None:
    """The expected Pattern the anomaly deviated from (``anomaly.pattern_id``)."""
    for pattern in patterns:
        if pattern.id == anomaly.pattern_id:
            return pattern
    return None


def _matching_templates(
    anomaly: Anomaly,
    scope: tuple[str, str],
    library: Sequence[HypothesisTemplate],
) -> list[HypothesisTemplate]:
    """Templates whose declared scope covers the anomaly's scope and class."""
    mental_model_id, purpose = scope
    return [
        template
        for template in library
        if template.scope_anomaly_class == anomaly.anomaly_class
        and mental_model_id in template.scope_mental_models
        and (not template.scope_purposes or purpose in template.scope_purposes)
    ]


def _facts(
    anomaly: Anomaly, scope: tuple[str, str], pattern: Pattern | None
) -> dict[str, object]:
    """Measured facts used to instantiate template placeholders (never invented)."""
    mental_model_id, purpose = scope
    return {
        "scope": f"{mental_model_id} para {purpose}",
        "anomaly_class": anomaly.anomaly_class,
        "deviation_score": anomaly.deviation_score,
        "frequency": pattern.frequency if pattern is not None else "desconocida",
    }


def generate(
    anomaly: Anomaly,
    contexts: Sequence[Context],
    patterns: Sequence[Pattern],
    library: Sequence[HypothesisTemplate] = HYPOTHESIS_TEMPLATE_LIBRARY,
) -> list[HypothesisCreate]:
    """Instantiate candidate Hypotheses for one anomaly (pure, no I/O).

    Returns one ``HypothesisCreate`` per matching template (>=2 when templates
    apply), each with non-empty ``predicted_consequences`` and
    ``falsification_criterion``. An anomaly with no applicable template - or an
    unresolved scope (missing Active Context) - yields an empty list: the caller
    counts it as ``no_templates`` and never emits a hypothesis without support.
    """
    scope = _anomaly_scope(anomaly, contexts)
    if scope is None:
        return []
    templates = _matching_templates(anomaly, scope, library)
    if not templates:
        return []

    pattern = _expected_pattern(anomaly, patterns)
    facts = _facts(anomaly, scope, pattern)
    creations: list[HypothesisCreate] = []

    for template in templates:
        description = template.description_template.format(**facts)
        consequences = [
            consequence.format(**facts) for consequence in template.consequence_templates
        ]
        falsification = template.falsification_templates[0].format(**facts)
        creations.append(
            HypothesisCreate(
                tenant_id=anomaly.tenant_id,
                anomaly_ids=[anomaly.id],
                pattern_ids=[pattern.id] if pattern is not None else [],
                description=description,
                predicted_consequences=consequences,
                falsification_criterion=falsification,
                coherence_score=template.coherence_estimate,
                status=STATUS_CANDIDATE,
            )
        )

    # Idempotence guarantee is handled by the deterministic hypothesis_id
    # (includes the description text), so two distinct candidate explanations
    # over the same anomaly always produce distinct ids.
    assert len(creations) >= 2, (
        "premature convergence: a scope must expose at least two competing "
        "templates (framework: premature convergence is a cognitive failure)"
    )
    return creations