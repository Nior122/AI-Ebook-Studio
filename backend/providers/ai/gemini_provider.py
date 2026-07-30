"""Google Gemini provider adapter (Generative Language REST API)."""

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


class GeminiProvider(AIProvider):
    """Google Gemini adapter using the REST generateContent API."""

    BASE_URL = "https://generativelanguage.googleapis.com"
    PROVIDER = "gemini"
    DISPLAY_NAME = "Google Gemini"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=120.0,
            headers={"Content-Type": "application/json"},
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
                "Google AI API key is not configured.", provider=self.PROVIDER
            )

    def _build_body(self, request: Any) -> dict[str, Any]:
        generation_config: dict[str, object] = {}
        body: dict[str, Any] = {
            "contents": [
                {"role": m.role, "parts": [{"text": m.content}]} for m in request.messages
            ],
            "generationConfig": generation_config,
        }
        if request.config.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.config.max_tokens
        if request.config.temperature is not None:
            generation_config["temperature"] = request.config.temperature
        if request.config.top_p is not None:
            generation_config["topP"] = request.config.top_p
        if request.system_prompt:
            body["systemInstruction"] = {"parts": [{"text": request.system_prompt}]}
        if request.config.json_mode:
            generation_config["responseMimeType"] = "application/json"
            if request.config.response_schema:
                generation_config["responseSchema"] = request.config.response_schema
        return body

    # ------------------------------------------------------------------
    async def health_check(self) -> bool:
        try:
            r = await self._client.get("/v1beta/models", params={"key": self._api_key})
            return r.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        try:
            r = await self._client.get("/v1beta/models", params={"key": self._api_key})
            if r.status_code == 200:
                return [
                    m["name"].split("/")[-1]
                    for m in r.json().get("models", [])
                    if "name" in m
                ]
        except Exception:
            pass
        return ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash-exp"]

    async def generate_text(self, request: Any) -> AIResponse:
        body = self._build_body(request)
        url = f"/v1beta/models/{request.model}:generateContent"
        start = time.perf_counter_ns()
        try:
            r = await self._client.post(url, json=body, params={"key": self._api_key})
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(str(exc), provider=self.PROVIDER) from exc
        except httpx.NetworkError as exc:
            raise ProviderUnavailableError(str(exc), provider=self.PROVIDER) from exc

        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        if r.status_code == 400:
            raise ProviderAuthenticationError(
                "Invalid Gemini API key or request.", provider=self.PROVIDER
            )
        if r.status_code == 429:
            raise ProviderRateLimitError("Rate limited by Gemini.", provider=self.PROVIDER)
        if r.status_code >= 500:
            raise ProviderUnavailableError(
                f"Gemini server error {r.status_code}.", provider=self.PROVIDER
            )
        if r.status_code != 200:
            raise ProviderResponseError(r.text, provider=self.PROVIDER)

        data = r.json()
        text = self._extract_text(data)
        usage = data.get("usageMetadata", {})
        return AIResponse(
            content=text,
            finish_reason=candidates_finish(data),
            provider=self.PROVIDER,
            model=request.model,
            usage=TokenUsage(
                input_tokens=usage.get("promptTokenCount", 0),
                output_tokens=usage.get("candidatesTokenCount", 0),
                total_tokens=usage.get("totalTokenCount", 0),
            ),
            metadata={"latency_ms": elapsed_ms, "raw": data},
        )

    async def generate_structured_output(
        self, request: Any, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        cfg = request.config
        cls_req = type(request)
        cls_cfg = type(cfg)
        response = await self.generate_text(
            cls_req(
                messages=request.messages,
                model=request.model,
                provider=request.provider,
                config=cls_cfg(
                    temperature=cfg.temperature,
                    max_tokens=cfg.max_tokens,
                    top_p=cfg.top_p,
                    stream=False,
                    json_mode=True,
                    timeout_seconds=cfg.timeout_seconds,
                    response_schema=schema or cfg.response_schema,
                ),
                system_prompt=request.system_prompt,
                user_id=request.user_id,
                project_id=request.project_id,
                workspace_id=request.workspace_id,
                metadata=request.metadata,
            )
        )
        try:
            return json.loads(response.content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ProviderResponseError(
                f"Gemini did not return valid JSON: {exc}", provider=self.PROVIDER
            ) from exc

    async def stream_text(self, request: Any) -> AsyncIterator[str]:
        body = self._build_body(request)
        url = f"/v1beta/models/{request.model}:streamGenerateContent"
        async with self._client.stream(
            "POST", url, json=body, params={"key": self._api_key}
        ) as r:
            if r.status_code != 200:
                raise ProviderResponseError(r.text, provider=self.PROVIDER)
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    for candidate in chunk.get("candidates", []):
                        for part in candidate.get("content", {}).get("parts", []):
                            if "text" in part:
                                yield part["text"]
                except (json.JSONDecodeError, KeyError):
                    continue

    async def count_tokens(self, text: str, model: str) -> int:
        return len(text) // 4

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        text = ""
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "text" in part:
                    text += part["text"]
        return text


def candidates_finish(data: dict[str, Any]) -> str | None:
    candidates = data.get("candidates", [])
    if not candidates:
        return None
    return candidates[0].get("finishReason")
