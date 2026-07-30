"""OpenAI provider adapter (Chat Completions API)."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog

from providers.ai.base import (
    AIProvider,
    AIResponse,
    ModelCapability,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    TokenUsage,
)

logger = structlog.get_logger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI adapter using the Chat Completions API."""

    BASE_URL = "https://api.openai.com/v1"
    PROVIDER = "openai"
    SUPPORTED = {
        ModelCapability.TEXT_GENERATION,
        ModelCapability.STRUCTURED_OUTPUT,
        ModelCapability.STREAMING,
        ModelCapability.VISION,
        ModelCapability.TOOL_CALLING,
    }

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._logger = structlog.get_logger(__name__)
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=120.0,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    @property
    def name(self) -> str:
        return self.PROVIDER

    @property
    def display_name(self) -> str:
        return "OpenAI"

    # ------------------------------------------------------------------
    def validate_configuration(self) -> None:
        if not self._api_key:
            raise ProviderConfigurationError(
                "OpenAI API key is not configured.", provider=self.PROVIDER
            )

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ProviderAuthenticationError(
                "OpenAI API key is missing.", provider=self.PROVIDER
            )
        return {"Authorization": f"Bearer {self._api_key}"}

    @staticmethod
    def _to_openai_messages(request: Any) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if request.system_prompt:
            msgs.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            msgs.append({"role": m.role, "content": m.content})
        return msgs

    @staticmethod
    def _normalize(data: dict[str, Any], provider: str) -> AIResponse:
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return AIResponse(
            content=choice.get("message", {}).get("content", ""),
            finish_reason=choice.get("finish_reason"),
            provider=provider,
            model=data.get("model", ""),
            usage=TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            metadata={"raw": data},
        )

    # ------------------------------------------------------------------
    async def health_check(self) -> bool:
        try:
            r = await self._client.get("/models", headers=self._headers())
            return r.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        try:
            r = await self._client.get("/models", headers=self._headers())
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", [])]
        except Exception:
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

    async def generate_text(self, request: Any) -> AIResponse:
        config = request.config
        body: dict[str, Any] = {
            "model": request.model,
            "messages": self._to_openai_messages(request),
            "stream": False,
        }
        if config.temperature is not None:
            body["temperature"] = config.temperature
        if config.max_tokens is not None:
            body["max_tokens"] = config.max_tokens
        if config.top_p is not None:
            body["top_p"] = config.top_p
        if config.frequency_penalty is not None:
            body["frequency_penalty"] = config.frequency_penalty
        if config.presence_penalty is not None:
            body["presence_penalty"] = config.presence_penalty
        if config.json_mode:
            body["response_format"] = {"type": "json_object"}

        start = time.perf_counter_ns()
        try:
            response = await self._client.post(
                "/chat/completions", headers=self._headers(), json=body
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(str(exc), provider=self.PROVIDER) from exc
        except httpx.NetworkError as exc:
            raise ProviderUnavailableError(str(exc), provider=self.PROVIDER) from exc

        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        data = self._raise_for_status(response)
        gen = self._normalize(data, self.PROVIDER)
        return AIResponse(
            content=gen.content,
            finish_reason=gen.finish_reason,
            provider=self.PROVIDER,
            model=gen.model,
            usage=gen.usage,
            metadata={**gen.metadata, "latency_ms": elapsed_ms},
        )

    async def generate_structured_output(
        self, request: Any, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        cfg = request.config
        body: dict[str, Any] = {
            "model": request.model,
            "messages": self._to_openai_messages(request),
            "stream": False,
        }
        if cfg.temperature is not None:
            body["temperature"] = cfg.temperature
        if cfg.max_tokens is not None:
            body["max_tokens"] = cfg.max_tokens
        if schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "structured_output", "schema": schema},
            }
        else:
            body["response_format"] = {"type": "json_object"}

        start = time.perf_counter_ns()
        try:
            response = await self._client.post(
                "/chat/completions", headers=self._headers(), json=body
            )
        except httpx.NetworkError as exc:
            raise ProviderUnavailableError(str(exc), provider=self.PROVIDER) from exc
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        data = self._raise_for_status(response)
        content = data["choices"][0]["message"].get("content", "{}")
        return self._parse_json(content, elapsed_ms)

    def stream_text(self, request: Any) -> AsyncIterator[str]:
        body = {
            "model": request.model,
            "messages": self._to_openai_messages(request),
            "stream": True,
        }
        if request.config.temperature is not None:
            body["temperature"] = request.config.temperature
        if request.config.max_tokens is not None:
            body["max_tokens"] = request.config.max_tokens

        async def _gen() -> AsyncIterator[str]:
            async with self._client.stream(
                "POST", "/chat/completions", headers=self._headers(), json=body
            ) as r:
                if r.status_code != 200:
                    raise ProviderResponseError(r.text, provider=self.PROVIDER)
                async for line in r.aiter_lines():
                    if not line or line.strip() == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            if delta.get("content"):
                                yield delta["content"]
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue

        return _gen()

    async def count_tokens(self, text: str, model: str) -> int:
        return max(1, len(text) // 4)

    # ------------------------------------------------------------------
    def _raise_for_status(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code == 401:
            raise ProviderAuthenticationError("Invalid OpenAI API key.", provider=self.PROVIDER)
        if response.status_code == 429:
            raise ProviderRateLimitError("Rate limited by OpenAI.", provider=self.PROVIDER)
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"OpenAI server error {response.status_code}.", provider=self.PROVIDER
            )
        if response.status_code != 200:
            raise ProviderResponseError(response.text, provider=self.PROVIDER)
        return response.json()

    @staticmethod
    def _parse_json(content: str, latency_ms: float) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ProviderResponseError(
                f"Provider did not return valid JSON: {exc}", provider="openai"
            ) from exc
