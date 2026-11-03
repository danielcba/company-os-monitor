"""ObservationEnricher — external LLM-assisted observation structuring (P1).

External, non-canonical capability (ADR-0002): an LLM helps structure RAW logs
into canonical Observations. It NEVER interprets logs as a conclusion (P1) — it
only extracts observable facts that are validated against the canonical
``ObservationCreate`` schema.

The LLM output is validated strictly:
  - each candidate must map to a well-formed ``ObservationCreate``
    (tenant_id, source_id, source_type, fact_type, fact_value, unit,
    quality_class Q1-Q4, raw_payload),
  - the enricher is the boundary: it cannot emit a judgment, anomaly, or
    recommendation (R3). Anomaly detection stays in the canonical Reason layer.
  - if the provider is unavailable or the output fails validation, the
    enricher returns an empty list (fallback) — the agent's minimal observation
    still flows without depending on the LLM.
"""
import uuid
from typing import Any

from pydantic import BaseModel, Field

from libs.cognitive_core.llm_provider import LlmProvider
from libs.perception.observation import ObservationCreate, QualityClass


class EnrichedObservationCandidate(BaseModel):
    """Estructura JSON que el LLM debe devolver (una por observación)."""

    source_type: str
    fact_type: str
    fact_value: dict[str, Any]
    unit: str
    quality_class: QualityClass
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class EnrichedObservationOutput(BaseModel):
    """Salida estructurada del LLM: lista de observaciones candidatas."""

    observations: list[EnrichedObservationCandidate]


class ObservationEnricher:
    """Estructura logs crudos → Observaciones canónicas (P1) usando un LlmProvider."""

    _SYSTEM_PROMPT = (
        "You are an observability data extractor. Given a raw log line from a "
        "monitored device, extract observable FACTS only. Never interpret the log "
        "as a conclusion, anomaly, or recommendation. For each fact return JSON "
        'with: source_type, fact_type, fact_value (object), unit, quality_class '
        '(one of Q1,Q2,Q3,Q4), raw_payload (the original log/context). Respond '
        'ONLY with JSON: {"observations": [...]}.'
    )

    def __init__(self, provider: LlmProvider[EnrichedObservationOutput]):
        self._provider = provider

    def validate_output(
        self, output: EnrichedObservationOutput
    ) -> bool:
        """Contrato: toda observación debe tener fact_type y quality_class válidos."""
        if output is None or not output.observations:
            return False
        for cand in output.observations:
            if not cand.fact_type or not cand.fact_type.strip():
                return False
            if cand.quality_class not in set(QualityClass):
                return False
        return True

    def _build_prompt(self, raw_log: str) -> str:
        return (
            f"{self._SYSTEM_PROMPT}\n\nRaw log: {raw_log}"
        )

    async def enrich(
        self,
        *,
        tenant_id: uuid.UUID,
        source_id: uuid.UUID,
        raw_log: str,
    ) -> list[ObservationCreate]:
        """Convierte un log crudo en Observaciones canónicas.

        Si el provider no está disponible o la salida no valida, devuelve []
        (fallback): nunca bloquea ni altera el flujo canónico (R3).
        """
        if not self._provider.available():
            return []

        messages = [
            {"role": "system", "content": self._SYSTEM_PROMPT},
            {"role": "user", "content": self._build_prompt(raw_log)},
        ]
        raw = await self._provider._chat_completion(
            messages,
            temperature=0.2,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        try:
            parsed = EnrichedObservationOutput.model_validate_json(raw)
        except Exception:  # noqa: BLE001 - invalid LLM output -> fallback
            return []
        if not self.validate_output(parsed):
            return []

        return [
            ObservationCreate(
                tenant_id=tenant_id,
                source_id=source_id,
                source_type=cand.source_type,
                fact_type=cand.fact_type,
                fact_value=cand.fact_value,
                unit=cand.unit,
                quality_class=cand.quality_class,
                raw_payload=cand.raw_payload,
            )
            for cand in parsed.observations
        ]
