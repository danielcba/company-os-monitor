"""Insight Generator - Reasoning/Restructure capability (pure functions, no I/O).

Input: a tenant's Hypotheses, its Anomalies and its Context stream + the
Insight Rule Library. Transform: resolve each Hypothesis to its ACTIVE Context
(traceability chain hypothesis -> anomaly -> context, same as the
recommendation layer) and, when the declared rule condition holds (multiple
competing hypotheses over the same Active Context), restructure the
relationship between those existing knowledge elements into ONE Insight per
competitive frame. Output: ``InsightCreate`` records - never facts, never
judgments, only a new organization of what was already available.

The generator NEVER reasons by itself: rules are declarative procedural memory
and every field is instantiated from measured facts. A single Hypothesis over
a context (or an unresolved scope) does NOT fire a rule: Insight cannot be
forced or scheduled (framework).
"""
from collections import defaultdict
from collections.abc import Sequence

from libs.perception.context import Context
from libs.procedural_memory.insight_rules import (
    INSIGHT_RULE_LIBRARY,
    InsightRule,
    build_insight,
)
from libs.reasoning.anomaly import Anomaly
from libs.reasoning.hypothesis import Hypothesis
from libs.reasoning.insight import InsightCreate


def _active_context(
    hypotheses: list[Hypothesis],
    anomalies: Sequence[Anomaly],
    contexts: Sequence[Context],
) -> dict[str, Context] | None:
    """Map each hypothesis to its ACTIVE Context (hypothesis -> anomaly -> context).

    Follows the traceability chain (the framework: insight refines Context and
    Hypothesis) and prefers the currently active activation (``is_active``);
    a hypothesis whose context is superseded (or missing) is NOT restructured.
    """
    anomaly_ids = {
        anomaly_id for hypothesis in hypotheses for anomaly_id in hypothesis.anomaly_ids
    }
    ctx_by_anomaly: dict[str, str] = {}
    for anomaly in anomalies:
        if anomaly.id in anomaly_ids:
            ctx_by_anomaly[str(anomaly.id)] = str(anomaly.context_id)
    active: dict[str, Context] = {}
    for context in contexts:
        if context.is_active and str(context.id) in ctx_by_anomaly.values():
            active[str(context.id)] = context
    return active


def _competitive_frames(
    tenant_id,
    hypotheses: Sequence[Hypothesis],
    anomalies: Sequence[Anomaly],
    contexts: Sequence[Context],
) -> list[tuple[Context, list[Hypothesis]]]:
    """Group hypotheses by their ACTIVE Context; return frames with >=2 hypotheses."""
    active = _active_context(list(hypotheses), anomalies, contexts)
    if not active:
        return []
    by_context: dict[str, list[Hypothesis]] = defaultdict(list)
    for hypothesis in hypotheses:
        anomaly_ids = set(hypothesis.anomaly_ids)
        ctx_ids = {
            str(anomaly.context_id)
            for anomaly in anomalies
            if anomaly.id in anomaly_ids
        }
        for ctx_id in ctx_ids:
            if ctx_id in active:
                by_context[ctx_id].append(hypothesis)
    frames: list[tuple[Context, list[Hypothesis]]] = []
    for ctx_id, grouped in by_context.items():
        if len(grouped) >= 2:
            frames.append((active[ctx_id], grouped))
    return frames


def generate_insights(
    tenant_id,
    hypotheses: Sequence[Hypothesis],
    anomalies: Sequence[Anomaly],
    contexts: Sequence[Context],
    rules: Sequence[InsightRule] = INSIGHT_RULE_LIBRARY,
) -> list[InsightCreate]:
    """Instantiate one Insight per competitive frame (pure, no I/O).

    Returns one ``InsightCreate`` per Active Context with >=2 competing
    hypotheses (the declared condition of the MVP rule). A context with a
    single hypothesis - or none - yields an empty list: the frame is not
    competitive and restructuring is not forced.
    """
    creations: list[InsightCreate] = []
    for context, grouped in _competitive_frames(tenant_id, hypotheses, anomalies, contexts):
        for rule in rules:
            if len(grouped) >= rule.min_hypotheses:
                creations.append(
                    build_insight(rule, tenant_id, context, sorted(
                        grouped, key=lambda h: h.id
                    ))
                )
    return creations