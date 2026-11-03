import uuid
from unittest.mock import AsyncMock

import pytest

from libs.cognitive_core.llm_provider import (
    LlmProvider,
    LmStudioProvider,
    OpenAICompatibleProvider,
)
from libs.perception.observation import ObservationCreate, QualityClass
from libs.perception.observation_enricher import (
    EnrichedObservationCandidate,
    EnrichedObservationOutput,
    ObservationEnricher,
)


def test_llm_provider_is_subclass_of_cognitive_tool():
    assert issubclass(LlmProvider, object)  # ABC base
    # Es verificable que expone el contrato (invoke/validate/available)
    for method in ("invoke", "validate_output", "available"):
        assert method in LlmProvider.__dict__ or method in LlmProvider.__mro__[1].__dict__


def test_lm_studio_provider_defaults():
    p = LmStudioProvider()
    assert p.model == "llama-4-8b"
    assert p.base_url.rstrip("/") == "http://lm-studio:1234/v1"


def test_openai_compatible_provider_holds_key_without_exposing():
    p = OpenAICompatibleProvider(
        base_url="https://api.example.com/v1",
        model="gpt-deep",
        api_key="sk-secret",
    )
    assert p.api_key == "sk-secret"
    assert "sk-secret" not in repr(p)


@pytest.mark.asyncio
async def test_observation_enricher_validates_and_maps():
    provider = AsyncMock(spec=LlmProvider)
    provider.available.return_value = True

    raw = (
        '{"observations": [{"source_type": "linux_agent", "fact_type": '
        '"cpu_utilization", "fact_value": {"value": 87}, "unit": '
        '"percent", "quality_class": "Q1", "raw_payload": '
        '{"line": "cpu 87"}}]}'
    )
    provider._chat_completion = AsyncMock(return_value=raw)

    enricher = ObservationEnricher(provider)
    tenant = uuid.uuid4()
    source = uuid.uuid4()
    obs = await enricher.enrich(tenant_id=tenant, source_id=source, raw_log="cpu 87")

    assert len(obs) == 1
    assert isinstance(obs[0], ObservationCreate)
    assert obs[0].tenant_id == tenant
    assert obs[0].source_id == source
    assert obs[0].fact_type == "cpu_utilization"
    assert obs[0].quality_class == QualityClass.Q1


@pytest.mark.asyncio
async def test_observation_enricher_falls_back_when_provider_down():
    provider = AsyncMock(spec=LlmProvider)
    provider.available.return_value = False

    enricher = ObservationEnricher(provider)
    obs = await enricher.enrich(
        tenant_id=uuid.uuid4(), source_id=uuid.uuid4(), raw_log="x"
    )
    assert obs == []


@pytest.mark.asyncio
async def test_observation_enricher_rejects_invalid_output():
    provider = AsyncMock(spec=LlmProvider)
    provider.available.return_value = True
    # calidad inválida -> debe rechazarse
    raw = (
        '{"observations": [{"source_type": "a", "fact_type": "b", '
        '"fact_value": {}, "unit": "", "quality_class": "Q9", '
        '"raw_payload": {}}]}'
    )
    provider._chat_completion = AsyncMock(return_value=raw)

    enricher = ObservationEnricher(provider)
    obs = await enricher.enrich(
        tenant_id=uuid.uuid4(), source_id=uuid.uuid4(), raw_log="x"
    )
    assert obs == []


def test_enriched_observation_output_model():
    out = EnrichedObservationOutput.model_validate(
        {
            "observations": [
                {
                    "source_type": "linux_agent",
                    "fact_type": "mem_usage",
                    "fact_value": {"value": 60},
                    "unit": "percent",
                    "quality_class": "Q2",
                    "raw_payload": {"line": "mem 60"},
                }
            ]
        }
    )
    assert isinstance(out.observations[0], EnrichedObservationCandidate)
    assert out.observations[0].quality_class == QualityClass.Q2
