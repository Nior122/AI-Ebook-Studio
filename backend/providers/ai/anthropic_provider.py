"""Anthropic provider adapter (Messages API)."""

from __future__ import annotations

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


class AnthropicProvider(AIProvider):
    """Anthropic adapter using the Messages API."""

    BASE_URL = "https://api.anthropic.com"
    PROVIDER = "anthropic"
    DISPLAY_NAME = "Anthropic"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
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
        return self.DISPLAY_NAME

    # ------------------------------------------------------------------
    def validate_configuration(self) -> None:
        if not self._api_key:
            raise ProviderConfigurationError(
                "Anthropic API key is not configured.", provider=self.PROVIDER
            )

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ProviderAuthenticationError(
                "Anthropic API key is missing.", provider=self.PROVIDER
            )
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

    @staticmethod
    def _to_anthropic_messages(
        request: Any,
    ) -> tuple[str | None, list[dict[str, str]]]:
        system = request.system_prompt
        msgs: list[dict[str, str]] = []
        for m in request.messages:
            msgs.append({"role": m.role, "content": m.content})
        return system, msgs

    # ------------------------------------------------------------------
    async def health_check(self) -> bool:
        try:
            r = await self._client.get("/v1/models", headers=self._headers())
            return r.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        try:
            r = await self._client.get("/v1/models", headers=self._headers())
            if r.status_code == 200:
                return [m["id"] for m in r.json().get("data", [])]
        except Exception:
            pass
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ]

    async def generate_text(self, request: Any) -> AIResponse:
        config = request.config
        system, messages = self._to_anthropic_messages(request)
        body: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": config.max_tokens or 4096,
        }
        if system:
            body["system"] = system
        if config.temperature is not None:
            body["temperature"] = config.temperature
        if config.json_mode:
            # Claude supports native structured output via tool-use or the
            # beta header; for simplicity we request JSON via a tool and parse.
            body["tools"] = [
                {
                    "name": "emit_json",
                    "description": "Return the result as a JSON object.",
                    "input_schema": request.config.response_schema
                    or {"type": "object", "properties": {}, "required": []},
                }
            ]
            body["tool_choice"] = {"type": "tool", "name": "emit_json"}

        start = time.perf_counter_ns()
        try:
            r = await self._client.post("/v1/messages", headers=self._headers(), json=body)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(str(exc), provider=self.PROVIDER) from exc
        except httpx.NetworkError as exc:
            raise ProviderUnavailableError(str(exc), provider=self.PROVIDER) from exc

        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        if r.status_code == 401:
            raise ProviderAuthenticationError("Invalid Anthropic API key.", provider=self.PROVIDER)
        if r.status_code == 429:
            raise ProviderRateLimitError("Rate limited by Anthropic.", provider=self.PROVIDER)
        if r.status_code >= 500:
            raise ProviderUnavailableError(
                f"Anthropic server error {r.status_code}.", provider=self.PROVIDER
            )
        if r.status_code != 200:
            raise ProviderResponseError(r.text, provider=self.PROVIDER)

        data = r.json()
        text = self._extract_text(data)
        usage = data.get("usage", {})
        return AIResponse(
            content=text,
            finish_reason=data.get("stop_reason"),
            provider=self.PROVIDER,
            model=data.get("model", ""),
            usage=TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            ),
            metadata={"latency_ms": elapsed_ms, "raw": data},
        )

    async def generate_structured_output(
        self, request: Any, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # Reuse generate_text with JSON-mode tool forcing enabled; the returned
        # response content already carries the JSON object string.
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
        import json

        try:
            return json.loads(response.content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ProviderResponseError(
                f"Anthropic did not return valid JSON: {exc}", provider=self.PROVIDER
            ) from exc

    async def stream_text(self, request: Any):
        """Stream Anthropic SSE events, yielding text deltas as they arrive."""
        config = request.config
        system, messages = self._to_anthropic_messages(request)
        body: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": config.max_tokens or 4096,
            "stream": True,
        }
        if system:
            body["system"] = system
        if config.temperature is not None:
            body["temperature"] = config.temperature
        try:
            async with self._client.stream(
                "POST", "/v1/messages", headers={**self._headers(), "anthropic-version": "2023-06-01"}, json=body,
            ) as r:
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        import json as _json

                        event = _json.loads(payload)
                    except Exception:
                        continue
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        piece = delta.get("text", "")
                        if piece:
                            yield piece
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(str(exc), provider=self.PROVIDER) from exc

    async def count_tokens(self, text: str, model: str) -> int:
        return len(text) // 4

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        import json

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                if block.get("name") == "emit_json":
                    text = json.dumps(block.get("input", {}))
        return text
