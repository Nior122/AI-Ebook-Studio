"""Generic OpenAI-compatible provider adapter.

This single adapter powers every OpenAI-compatible endpoint by allowing
``base_url`` / ``api_key`` / ``default_model`` to be configured at runtime. It
is the foundation for:

* ``custom_openai``  — user-supplied base URL
* ``nvidia_nim``     — NVIDIA NIM
* ``groq``           — Groq
* ``openrouter``     — OpenRouter
* ``fireworks`` / ``cerebras`` / ``together`` — any compatible gateway

Provider-specific adapters simply subclass this with a fixed ``BASE_URL`` and
``PROVIDER`` id, so there is no duplicated request/response logic.
"""

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


class OpenAICompatibleProvider(AIProvider):
    """Base adapter for any OpenAI Chat Completions compatible endpoint."""

    BASE_URL = "https://api.openai.com/v1"
    PROVIDER = "openai_compatible"
    DISPLAY_NAME = "OpenAI-Compatible"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or self.BASE_URL).rstrip("/")
        self._default_model = default_model
        self._timeout = timeout_seconds
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout_seconds,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    @property
    def name(self) -> str:
        return self.PROVIDER

    @property
    def display_name(self) -> str:
        return self.DISPLAY_NAME

    # ------------------------------------------------------------------
    def validate_configuration(self) -> None:
        if not self._api_key:
            raise ProviderConfigurationError(
                f"{self.DISPLAY_NAME} API key is not configured.", provider=self.PROVIDER
            )

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ProviderAuthenticationError(
                f"{self.DISPLAY_NAME} API key is missing.", provider=self.PROVIDER
            )
        return {"Authorization": f"Bearer {self._api_key}"}

    def _resolve_model(self, model: str) -> str:
        # When a provider-specific model id is supplied without a slash, keep it.
        # If the whole request only gave a bare name and we have a default, use it.
        if model:
            return model
        if self._default_model:
            return self._default_model
        raise ProviderConfigurationError(
            "No model specified for OpenAI-compatible request.", provider=self.PROVIDER
        )

    @staticmethod
    def _to_messages(request: Any) -> list[dict[str, str]]:
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
            data = r.json()
            models = data.get("data")
            if isinstance(models, list):
                return [m["id"] for m in models if "id" in m]
        except Exception:
            pass
        # Some gateways (e.g. NVIDIA NIM) expose /models differently; fall back
        # to the configured default if present.
        return [self._default_model] if self._default_model else []

    async def generate_text(self, request: Any) -> AIResponse:
        config = request.config
        model = self._resolve_model(request.model)
        body: dict[str, Any] = {
            "model": model,
            "messages": self._to_messages(request),
            "stream": False,
        }
        if config.temperature is not None:
            body["temperature"] = config.temperature
        if config.max_tokens is not None:
            body["max_tokens"] = config.max_tokens
        if config.top_p is not None:
            body["top_p"] = config.top_p
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
        config = request.config
        model = self._resolve_model(request.model)
        body: dict[str, Any] = {
            "model": model,
            "messages": self._to_messages(request),
            "stream": False,
        }
        if config.temperature is not None:
            body["temperature"] = config.temperature
        if config.max_tokens is not None:
            body["max_tokens"] = config.max_tokens
        if schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "structured_output", "schema": schema},
            }
        else:
            body["response_format"] = {"type": "json_object"}

        try:
            response = await self._client.post(
                "/chat/completions", headers=self._headers(), json=body
            )
        except httpx.NetworkError as exc:
            raise ProviderUnavailableError(str(exc), provider=self.PROVIDER) from exc
        data = self._raise_for_status(response)
        content = data["choices"][0]["message"].get("content", "{}")
        return self._parse_json(content)

    def stream_text(self, request: Any) -> AsyncIterator[str]:
        model = self._resolve_model(request.model)
        body = {
            "model": model,
            "messages": self._to_messages(request),
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
            raise ProviderAuthenticationError(
                f"Invalid {self.DISPLAY_NAME} API key.", provider=self.PROVIDER
            )
        if response.status_code == 429:
            raise ProviderRateLimitError(
                f"Rate limited by {self.DISPLAY_NAME}.", provider=self.PROVIDER
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"{self.DISPLAY_NAME} server error {response.status_code}.",
                provider=self.PROVIDER,
            )
        if response.status_code != 200:
            raise ProviderResponseError(response.text, provider=self.PROVIDER)
        return response.json()

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ProviderResponseError(
                f"Provider did not return valid JSON: {exc}", provider="openai_compatible"
            ) from exc


# ---------------------------------------------------------------------------
# Concrete OpenAI-compatible providers
# ---------------------------------------------------------------------------
class OpenRouterProvider(OpenAICompatibleProvider):
    BASE_URL = "https://openrouter.ai/api/v1"
    PROVIDER = "openrouter"
    DISPLAY_NAME = "OpenRouter"


class GroqProvider(OpenAICompatibleProvider):
    BASE_URL = "https://api.groq.com/openai/v1"
    PROVIDER = "groq"
    DISPLAY_NAME = "Groq"


class NvidiaNimProvider(OpenAICompatibleProvider):
    BASE_URL = "https://integrate.api.nvidia.com/v1"
    PROVIDER = "nvidia_nim"
    DISPLAY_NAME = "NVIDIA NIM"


class CustomOpenAIProvider(OpenAICompatibleProvider):
    """User-configured generic OpenAI-compatible endpoint."""

    PROVIDER = "custom_openai"
    DISPLAY_NAME = "Custom OpenAI-Compatible"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        if not base_url:
            raise ProviderConfigurationError(
                "custom_openai requires a base_url.", provider=self.PROVIDER
            )
        super().__init__(
            api_key,
            base_url=base_url,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
        )

    def validate_configuration(self) -> None:
        if not self._base_url:
            raise ProviderConfigurationError(
                "custom_openai requires a base_url.", provider=self.PROVIDER
            )
        # API key is optional for some local/open gateways.
