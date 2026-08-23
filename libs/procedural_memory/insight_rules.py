"""Insight Rules - declarative restructuring rules (Reasoning/Restructure).

The Insight Rule Library is procedural memory (P3): a catalogue of declarative
rules that detect when the current frame is competitive and restructure the
relationship between existing knowledge elements (the framework's Insight
concept: "Detect when the current frame fails repeatedly, trigger restructuring
of the mental model, record the transformation that produced the insight").

Rules never reason by themselves: they only reorganize knowledge that is
already available (prior_understanding + description are instantiated from
measured facts - context scope, hypothesis ids, anomaly ids, hypothesis
descriptions), never add facts, never assert causation and never judge. An
Insight "cannot be forced or scheduled": a rule fires ONLY when its declared
condition is met by the existing knowledge (the MVP rule fires when the frame
is genuinely competitive: multiple candidate hypotheses coexist over the same
Active Context, which per the framework means the frame has not converged).

Placeholders instantiated with measured facts:
  ``{scope}``        - ``{mental_model} para {purpose}`` of the Active Context
  ``{context_id}``   - id of the Active Context being restructured
  ``{n}``            - number of restructured hypotheses
  ``{anomaly_ids}``  - the anomalies the hypotheses account for
  ``{descriptions}`` - the prior hypothesis descriptions (verbatim, "; "-joined)
"""
from dataclasses import dataclass

COMPETITIVE_FRAME_MIN_HYPOTHESES: int = 2

from libs.perception.context import Context
from libs.reasoning.hypothesis import Hypothesis
from libs.reasoning.insight import InsightCreate

# The MVP frame: a single observed deviation of an Active Context that the
# system explains with multiple competing hypotheses. Restructuring it means
# organizing those explanations as alternative interpretations of the same
# deviation instead of independent problems.
FRAME_SINGLE_DEVIATION_MULTI_EXPLANATION = "single-deviation-multi-explanation"


@dataclass(frozen=True)
class InsightRule:
    """Declarative definition of one restructuring rule (procedural memory).

    ``rule_id`` is versioned (``_v1``/``_v2``): revising a rule means
    publishing a NEW version, never mutating a published one. ``min_hypotheses``
    is the declared condition that must be met for the frame to be considered
    competitive (Insight cannot be forced: below it the rule does not fire).
    ``description_template``/``prior_understanding_template``/``frame`` define
    the restructuring that the rule produces from measured facts only.
    """

    rule_id: str
    name: str
    min_hypotheses: int = 2
    description_template: str = ""
    prior_understanding_template: str = ""
    frame: str = FRAME_SINGLE_DEVIATION_MULTI_EXPLANATION

    def __post_init__(self) -> None:
        if self.min_hypotheses < COMPETITIVE_FRAME_MIN_HYPOTHESES:
            raise ValueError("min_hypotheses must be >= 2")  # noqa: TRY003
        if not self.description_template.strip():
            raise ValueError("description_template must not be empty")  # noqa: TRY003
        if not self.prior_understanding_template.strip():
            raise ValueError("prior_understanding_template must not be empty")  # noqa: TRY003
        if not self.frame.strip():
            raise ValueError("frame must not be empty")  # noqa: TRY003


def _scope(context: Context) -> str:
    """``{mental_model_id} para {purpose}`` of the Active Context (measured)."""
    return f"{context.mental_model_id} para {context.purpose}"


def _anomaly_ids(hypotheses: list[Hypothesis]) -> list[str]:
    """Union of the anomaly ids the restructured hypotheses account for."""
    ordered: set[str] = set()
    for hypothesis in hypotheses:
        ordered.update(str(anomaly_id) for anomaly_id in hypothesis.anomaly_ids)
    return sorted(ordered)


def _descriptions(hypotheses: list[Hypothesis]) -> str:
    """Verbatim prior hypothesis descriptions (the knowledge being restructured)."""
    return "; ".join(hypothesis.description for hypothesis in hypotheses)


def build_insight(
    rule: InsightRule,
    tenant_id,
    context: Context,
    hypotheses: list[Hypothesis],
) -> InsightCreate:
    """Instantiate one restructuring over measured facts (pure, no I/O).

    ``hypotheses`` must all belong to ``context`` (same Active Context) and the
    rule condition (``min_hypotheses``) must hold; the caller enforces it. All
    fields derive from existing knowledge only: the description is the new
    organization of what was already available, ``prior_understanding`` records
    the verbatim prior explanations (the transformation journal) and
    ``mental_model_update`` is a declarative, factual update to the active
    mental model - never a claim beyond the measured facts.
    """
    facts = {
        "scope": _scope(context),
        "context_id": str(context.id),
        "n": len(hypotheses),
        "anomaly_ids": ", ".join(_anomaly_ids(hypotheses)),
        "descriptions": _descriptions(hypotheses),
    }
    return InsightCreate(
        tenant_id=tenant_id,
        context_id=context.id,
        hypothesis_ids=[hypothesis.id for hypothesis in hypotheses],
        description=rule.description_template.format(**facts),
        prior_understanding=rule.prior_understanding_template.format(**facts),
        mental_model_update={
            "frame": rule.frame,
            "context_id": str(context.id),
            "scope": facts["scope"],
            "hypothesis_ids": [str(h.id) for h in hypotheses],
            "anomaly_ids": _anomaly_ids(hypotheses),
        },
    )


# ---------------------------------------------------------------------------
# The MVP rule library (procedural memory; publish a new version, never mutate)
# ---------------------------------------------------------------------------
INSIGHT_RULE_LIBRARY: tuple[InsightRule, ...] = (
    InsightRule(
        rule_id="competitive_frame_v1",
        name="Competitive frame resolution",
        min_hypotheses=2,
        description_template=(
            "El marco actual mantiene {n} hipótesis candidatas en competencia "
            "sobre el scope {scope} (contexto {context_id}): la explicación no "
            "ha convergido prematuramente en una única causa. La organización "
            "del conocimiento se reestructura tratando esas {n} explicaciones "
            "como interpretaciones alternativas de una misma desviación "
            "observada (anomalías {anomaly_ids}) en lugar de problemas "
            "independientes."
        ),
        prior_understanding_template=(
            "Comprensión previa: {n} hipótesis tratadas de forma independiente "
            "sobre el scope {scope} - {descriptions}"
        ),
        frame=FRAME_SINGLE_DEVIATION_MULTI_EXPLANATION,
    ),
)