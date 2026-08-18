"""Unit tests for the LM Studio Hypothesis Tool (external, ADR-0002).

Covers the falsification contract enforced by ``validate_output`` (EVERY
hypothesis must carry a non-empty falsification criterion) and the canonical
fallback behavior when LM Studio is unavailable: the tool never breaks the
flow - it just returns False from ``available()`` and the service stays on the
internal template library.
"""
import uuid

from libs.cognitive_core.lm_studio_hypothesis_tool import (
    LMStudioHypothesisOutput,
    LMStudioHypothesisTool,
)
from libs.reasoning.hypothesis import STATUS_CANDIDATE, HypothesisCreate

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
ANOMALY_ID = uuid.UUID("00000000-0000-0000-0000-00000000000a")


def make_hypothesis(*, falsification: str = "") -> HypothesisCreate:
    return HypothesisCreate(
        tenant_id=TENANT,
        anomaly_ids=[ANOMALY_ID],
        pattern_ids=[],
        description="Hipótesis candidata.",
        predicted_consequences=["Consecuencia observable."],
        falsification_criterion=falsification,
        coherence_score=0.5,
        status=STATUS_CANDIDATE,
    )


def test_validate_output_rejects_hypothesis_without_falsification():
    tool = LMStudioHypothesisTool(base_url="http://127.0.0.1:1/v1")
    assert tool.validate_output(
        [make_hypothesis(falsification="Criterio concreto y observable.")]
    ) is True
    assert tool.validate_output([make_hypothesis(falsification="")]) is False
    assert tool.validate_output([make_hypothesis(falsification="   ")]) is False
    assert tool.validate_output([]) is True  # no output -> vacuous truth, caller keeps templates


def test_validate_output_enforces_contract_on_all_hypotheses():
    tool = LMStudioHypothesisTool(base_url="http://127.0.0.1:1/v1")
    good = make_hypothesis(falsification="Criterio.")
    bad = make_hypothesis(falsification="")
    assert tool.validate_output([good, good]) is True
    assert tool.validate_output([good, bad]) is False


def test_available_is_false_when_lm_studio_is_down():
    tool = LMStudioHypothesisTool(base_url="http://127.0.0.1:1/v1")
    assert tool.available() is False


def test_pydantic_parsing_of_structured_output():
    raw = (
        '{"hypotheses": ['
        '  {"description": "Un actor externo podría estar sondeando credenciales.",'
        '   "predicted_consequences": ["Más intentos fallidos."],'
        '   "falsification_criterion": "Si los intentos provienen de un único origen."},'
        '  {"description": "Un bucle de reintentos podría estar activo.",'
        '   "predicted_consequences": ["Reintentos periódicos."],'
        '   "falsification_criterion": "Si no hay reintentos periódicos."}'
        "]}"
    )
    parsed = LMStudioHypothesisOutput.model_validate_json(raw)
    assert len(parsed.hypotheses) == 2
    assert all(h.falsification_criterion for h in parsed.hypotheses)


def test_build_prompt_is_structured_and_factual():
    tool = LMStudioHypothesisTool(base_url="http://127.0.0.1:1/v1")
    prompt = tool._build_prompt(
        {
            "scope": "resource_pressure para infrastructure_health",
            "anomaly_class": "point",
            "deviation_score": 2.5,
            "anomaly_description": "desviación",
            "context_summary": "activación",
            "pattern_summary": "diaria",
        }
    )
    assert "resource_pressure" in prompt
    assert "2.5" in prompt
    assert "falsification_criterion" in prompt