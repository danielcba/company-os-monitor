"""LMStudioHypothesisTool - external cognitive tool (ADR-0002).

LM Studio is an EXTERNAL, NON-CANONICAL capability (ADR-0002): it is a tool
for adding candidate-explanations diversity, never a source of truth. Every
tool output must pass structured parsing (Pydantic) and re-enter the canonical
flow as ``HypothesisCreate`` records - it never bypasses the cognitive
pipeline. The canonical flow ALWAYS starts from the internal template library;
LM Studio only ADDS hypotheses when ``available()`` is true.

The tool enforces the same contracts as the internal generator: every
hypothesis carries a non-empty ``falsification_criterion`` (the concrete
outcome that would demonstrate it false - mandatory in ALL hypotheses). If LM
Studio is not running, ``available()`` returns False and the caller falls back
to templates only (the canonical flow NEVER stays without output).

No Confidence is computed here (Sprint 8); ``coherence_score`` for LM Studio
candidates is a documented declarative placeholder (0.5), never a measured or
calibrated value.
"""
import asyncio
import json
import uuid

import aiohttp
from pydantic import BaseModel, Field

from libs.cognitive_core.cognitive_tool import CognitiveTool
from libs.reasoning.hypothesis import STATUS_CANDIDATE, HypothesisCreate

_HTTP_OK = 200


class LMStudioHypothesisCandidate(BaseModel):
    """Structured output of one LM Studio hypothesis candidate.

    ``description`` is TENTATIVE explanation language (the prompt forbids
    asserted causation); ``predicted_consequences`` are observable predictions
    and ``falsification_criterion`` is the concrete observable outcome that
    would falsify it.
    """

    description: str
    predicted_consequences: list[str] = Field(min_length=1)
    falsification_criterion: str


class LMStudioHypothesisOutput(BaseModel):
    """Parsed structured response from LM Studio (JSON -> Pydantic)."""

    hypotheses: list[LMStudioHypothesisCandidate]


DEFAULT_LM_STUDIO_URL = "http://lm-studio:1234/v1"
DEFAULT_MODEL = "llama-4-8b"

_SYSTEM_PROMPT = (
    "You are a hypothesis generator for an observability system. Propose up to "
    "3 COMPETING candidate explanations for the given anomaly. Each hypothesis "
    "must (1) be tentative, phrased as 'could/podría', NEVER assert causation as "
    "fact; (2) include predicted_consequences (observable, falsifiable); (3) "
    "include a falsification_criterion: the concrete observable outcome that "
    "would prove it false. Respond ONLY with JSON: "
    '{"hypotheses": [{"description": str, "predicted_consequences": [str], '
    '"falsification_criterion": str}]}.'
)


class LMStudioHypothesisTool(CognitiveTool[list[HypothesisCreate]]):
    """LM Studio as an external hypothesis-diversity tool (ADR-0002).

    ``invoke`` expects a structured input dict with the anomaly facts and the
    canonical context (tenant/anomaly/pattern ids); it POSTs a structured
    prompt, parses the JSON response with Pydantic, and maps it into
    ``HypothesisCreate`` records (canonical representation). ``validate_output``
    enforces the falsification contract on ALL hypotheses. ``available`` probes
    the LM Studio endpoint.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str = DEFAULT_MODEL,
        request_timeout_s: float = 30.0,
    ):
        self.base_url = (base_url or DEFAULT_LM_STUDIO_URL).rstrip("/")
        self.model = model
        self.request_timeout_s = request_timeout_s

    def available(self) -> bool:
        """Probe LM Studio (GET /v1/models). Non-canonical; never blocks the flow."""
        try:
            async def _probe() -> bool:
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(
                            f"{self.base_url}/models", timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            return resp.status == _HTTP_OK
                    except (aiohttp.ClientError, OSError):
                        return False

            return asyncio.run(_probe())
        except Exception:  # noqa: BLE001 - tool availability must never raise
            return False

    def validate_output(self, output: list[HypothesisCreate]) -> bool:
        """Falsification contract: EVERY hypothesis must have a criterion."""
        return all(
            bool(h.falsification_criterion and h.falsification_criterion.strip())
            for h in output
        )

    def _build_prompt(self, input: dict) -> str:
        facts = {
            "scope": input.get("scope", "desconocido"),
            "anomaly_class": input.get("anomaly_class", "point"),
            "deviation_score": input.get("deviation_score"),
            "anomaly_description": input.get("anomaly_description", ""),
            "context_summary": input.get("context_summary", ""),
            "pattern_summary": input.get("pattern_summary", ""),
        }
        return (
            f"{_SYSTEM_PROMPT}\n\nAnomaly facts: {json.dumps(facts, ensure_ascii=False)}"
        )

    async def invoke(self, input: dict) -> list[HypothesisCreate]:
        """Call LM Studio, parse the JSON response, map to canonical HypothesisCreate."""
        tenant_id = uuid.UUID(str(input["tenant_id"]))
        anomaly_ids = [uuid.UUID(str(x)) for x in input["anomaly_ids"]]
        pattern_ids = [uuid.UUID(str(x)) for x in input.get("pattern_ids", [])]

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": self._build_prompt(input)},
            ],
            "temperature": 0.7,
            "max_tokens": 512,
            "response_format": {"type": "json_object"},
        }

        async with aiohttp.ClientSession() as session, session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.request_timeout_s),
        ) as resp:
            resp.raise_for_status()
            body = await resp.json()

        raw = body["choices"][0]["message"]["content"]
        parsed = LMStudioHypothesisOutput.model_validate_json(raw)

        return [
            HypothesisCreate(
                tenant_id=tenant_id,
                anomaly_ids=anomaly_ids,
                pattern_ids=pattern_ids,
                description=candidate.description,
                predicted_consequences=candidate.predicted_consequences,
                falsification_criterion=candidate.falsification_criterion,
                coherence_score=0.5,
                status=STATUS_CANDIDATE,
            )
            for candidate in parsed.hypotheses
        ]