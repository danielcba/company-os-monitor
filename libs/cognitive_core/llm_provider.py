"""LlmProvider — external LLM provider abstraction (ADR-0002).

External, non-canonical capability (ADR-0002): an LLM provider (local: LM Studio /
ollama, or remote: ChatGPT / Gemini / DeepSeek / Claude via an OpenAI-compatible
endpoint) is a TOOL that assists the canonical cognitive flow. It is never a
source of truth and never bypasses the cognitive pipeline (R3).

Every provider implements the same ``CognitiveTool`` contract:
  - ``available()`` probes health (never blocks the canonical flow),
  - ``invoke(input)`` sends a structured prompt and returns structured output,
  - ``validate_output(output)`` enforces the cognitive contract.

The canonical flow ALWAYS keeps its internal (template/rule-based) path; the LLM
only ADDS structured candidates when ``available()`` is true. If no provider is
available, callers fall back to the internal path — the system never stays
without output and never depends on an external model.
"""
import asyncio
from abc import ABC
from typing import Any, Generic, TypeVar

import aiohttp

from libs.cognitive_core.cognitive_tool import CognitiveTool

T = TypeVar("T")

_HTTP_OK = 200


class LlmProvider(CognitiveTool[T], ABC, Generic[T]):
    """Abstracción para cualquier proveedor LLM (local/remoto, OpenAI-compatible).

    Subclases deben definir ``model``, ``base_url`` y cómo construir el payload.
    El contrato heredado (invoke/validate_output/available) se mantiene.
    """

    def __init__(self, base_url: str, model: str, request_timeout_s: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.request_timeout_s = request_timeout_s

    def __repr__(self) -> str:
        # No expone api_key ni secretos (seguridad).
        return f"<{self.__class__.__name__} model={self.model!r}>"

    async def invoke(self, input: dict) -> T:
        """Implementación concreta por defecto: las subclases definen el
        contrato específico (pero queda instanciable)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} debe implementar invoke()"
        )

    async def _chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
        response_format: dict | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        async with aiohttp.ClientSession() as session, session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.request_timeout_s),
        ) as resp:
            resp.raise_for_status()
            body = await resp.json()

        return body["choices"][0]["message"]["content"]

    def available(self) -> bool:
        """Probe GET /v1/models (síncrono, contrato CognitiveTool).
        Non-canonical; never blocks the flow."""
        try:
            async def _probe() -> bool:
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(
                            f"{self.base_url}/models",
                            timeout=aiohttp.ClientTimeout(total=5),
                        ) as resp:
                            return resp.status == _HTTP_OK
                    except (aiohttp.ClientError, OSError):
                        return False

            return asyncio.run(_probe())
        except Exception:  # noqa: BLE001 - availability must never raise
            return False

    def validate_output(self, output: T) -> bool:
        """Por defecto, considera válido cualquier output estructurado. Las
        subclases concretas sobreescriben con la validación de su contrato."""
        return output is not None


class LmStudioProvider(LlmProvider[T]):
    """Provider local (LM Studio / ollama) compatible OpenAI."""

    def __init__(
        self,
        base_url: str = "http://lm-studio:1234/v1",
        model: str = "llama-4-8b",
        request_timeout_s: float = 30.0,
    ):
        super().__init__(base_url, model, request_timeout_s)


class OpenAICompatibleProvider(LlmProvider[T]):
    """Provider remoto compatible OpenAI (ChatGPT, Gemini, DeepSeek, Claude).

    ``api_key`` se pasa explícitamente; se envía como Bearer token. No se
    registra ni persiste en logs.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        request_timeout_s: float = 30.0,
    ):
        super().__init__(base_url, model, request_timeout_s)
        self.api_key = api_key

    async def _chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
        response_format: dict | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with aiohttp.ClientSession(headers=headers) as session, session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.request_timeout_s),
        ) as resp:
            resp.raise_for_status()
            body = await resp.json()

        return body["choices"][0]["message"]["content"]
