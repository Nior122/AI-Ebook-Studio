"""Ollama provider adapter (local models)."""

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
    ProviderResponseError,
    ProviderUnavailableError,
    TokenUsage,
)

logger = structlog.get_logger(__name__)


class OllamaProvider(AIProvider):
    """Ollama adapter for self-hosted models.

    Assumes an Ollama server is reachable at ``base_url`` (default
    ``http://localhost:11434``). No API key is required.
    """

    PROVIDER = "ollama"
    DISPLAY_NAME = "Ollama (local)"

    def __init__(
        self, base_url: str = "http://localhost:11434", api_key: str | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=300.0,
            headers={"Content-Type": "application/json"},
        )

    @property
    def name(self) -> str:
        return self.PROVIDER

    @property
    def display_name(self) -> str:
        return self.DISPLAY_NAME

    def validate_configuration(self) -> None:  # local server; nothing required
        return None

    @staticmethod
    def _to_messages(request: Any) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if request.system_prompt:
            msgs.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            msgs.append({"role": m.role, "content": m.content})
        return msgs

    async def health_check(self) -> bool:
        try:
            r = await self._client.get("/api/tags")
            return r.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> list[str]:
        try:
            r = await self._client.get("/api/tags")
            if r.status_code == 200:
                return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            pass
        return ["llama3.2", "llama3.1", "mistral", "phi4"]

    async def generate_text(self, request: Any) -> AIResponse:
        config = request.config
        body: dict[str, Any] = {
            "model": request.model,
            "messages": self._to_messages(request),
            "stream": False,
        }
        options: dict[str, Any] = {}
        if config.temperature is not None:
            options["temperature"] = config.temperature
        if config.max_tokens is not None:
            options["num_predict"] = config.max_tokens
        if options:
            body["options"] = options

        start = time.perf_counter_ns()
        try:
            r = await self._client.post("/api/chat", json=body)
        except httpx.NetworkError as exc:
            raise ProviderUnavailableError(str(exc), provider=self.PROVIDER) from exc

        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        if r.status_code != 200:
            raise ProviderResponseError(r.text, provider=self.PROVIDER)

        data = r.json()
        message = data.get("message", {})
        return AIResponse(
            content=message.get("content", ""),
            finish_reason="stop" if data.get("done") else None,
            provider=self.PROVIDER,
            model=request.model,
            usage=TokenUsage(),
            metadata={"latency_ms": elapsed_ms, "raw": data},
        )

    async def generate_structured_output(
        self, request: Any, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # Ollama has no native structured output; request JSON via prompt.
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
                f"Ollama did not return valid JSON: {exc}", provider=self.PROVIDER
            ) from exc

    async def stream_text(self, request: Any) -> AsyncIterator[str]:
        body = {
            "model": request.model,
            "messages": self._to_messages(request),
            "stream": True,
        }
        async with self._client.stream("POST", "/api/chat", json=body) as r:
            if r.status_code != 200:
                raise ProviderResponseError(str(r.status_code), provider=self.PROVIDER)
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    msg = chunk.get("message", {})
                    if "content" in msg:
                        yield msg["content"]
                except (json.JSONDecodeError, KeyError):
                    continue

    async def count_tokens(self, text: str, model: str) -> int:
        return len(text) // 4
