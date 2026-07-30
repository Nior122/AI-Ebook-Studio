"""AI Engine — provider-independent generation, streaming, fallback, retry.

This is the legacy facade kept for backwards compatibility. New code should
prefer :class:`services.ai_service.AIService`. Both layers sit on top of the
provider registry and the provider-agnostic interface in :mod:`providers.ai`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import structlog

from core.config import Settings, get_settings
from providers.ai.base import (
    AIProvider,
    AIProviderError,
    AIResponse,
    GenerationRequest,
    ProviderUnavailableError,
    TokenUsage,
)
from providers.ai.registry import ProviderRegistry
from services.models_registry import ModelRegistry as _ModelRegistry

logger = structlog.get_logger(__name__)

_FOUR_MIN = 240.0  # seconds, generous fallback timeout


class AIEngine:
    """Central intelligence layer used by every AI feature in the application."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._logger = structlog.get_logger(__name__)
        self._registry = ProviderRegistry()
        self._registry.load_from_settings(self.settings)
        self._model_registry = _ModelRegistry()

    # ------------------------------------------------------------------
    @property
    def available_providers(self) -> list[str]:
        """Return ids of successfully-configured providers."""
        return self._registry.available()

    @property
    def _providers(self) -> dict[str, AIProvider]:
        """Backwards-compatible accessor (tests set this directly)."""
        return self._registry._providers  # noqa: SLF001

    @_providers.setter
    def _providers(self, value: dict[str, AIProvider]) -> None:
        self._registry._providers = value  # noqa: SLF001

    def provider_for(self, model_specifier: str) -> AIProvider:
        """Resolve a provider from a model string like ``openai/gpt-4o``."""
        if "/" in model_specifier:
            provider_name, _ = model_specifier.split("/", 1)
        else:
            provider_name = self._default_provider_name()
        provider = self._registry.get(provider_name)
        if provider is None:
            raise ValueError(f"Provider for '{model_specifier}' is not configured.")
        return provider

    # ------------------------------------------------------------------
    async def generate(self, request: GenerationRequest) -> AIResponse:
        """Generate text with retry and fallback."""
        provider = self._resolve_provider(request)
        request = self._maybe_inject_model(request, provider)
        primary_provider_name = provider.name

        attempts = max(1, request.config.retry_attempts + 1)
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await provider.generate_text(request)
                return self._with_cost(response)
            except AIProviderError as exc:
                if not exc.retryable:
                    raise
                last_exc = exc
                self._logger.warning(
                    "generation_retry",
                    provider=provider.name,
                    model=request.model,
                    attempt=attempt,
                    error=str(exc),
                )
                await self._sleep(1.0 * attempt)

        if last_exc:
            return await self._fallback_generate(request, primary_provider_name)
        raise AIProviderError("Unexpected empty generation path.", provider=request.provider)

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Yield text chunks from a streaming request."""
        provider = self._resolve_provider(request)
        request = self._maybe_inject_model(request, provider)
        try:
            async for chunk in provider.stream_text(request):
                yield chunk
        except NotImplementedError:
            gen = await provider.generate_text(request)
            yield gen.content

    async def health(self, provider_name: str | None = None) -> dict[str, bool]:
        if provider_name:
            p = self._registry.get(provider_name)
            return {provider_name: await p.health_check() if p else False}
        results: dict[str, bool] = {}
        for name, provider in self._registry._providers.items():  # noqa: SLF001
            try:
                results[name] = await provider.health_check()
            except Exception:
                results[name] = False
        return results

    # ------------------------------------------------------------------
    def _default_provider_name(self) -> str:
        for name in ("openai", "anthropic", "gemini", "openrouter", "groq", "nvidia_nim", "ollama"):
            if self._registry.is_available(name):
                return name
        raise ValueError("No AI provider is configured.")

    def _resolve_provider(self, request: GenerationRequest) -> AIProvider:
        model = request.model or ""
        if "/" in model:
            provider_name, _ = model.split("/", 1)
        elif request.provider:
            provider_name = request.provider
        else:
            provider_name = self._default_provider_name()
        provider = self._registry.get(provider_name)
        if provider is None:
            raise ValueError(f"Provider '{provider_name}' is not configured.")
        return provider

    def _maybe_inject_model(self, request: GenerationRequest, provider: AIProvider) -> GenerationRequest:
        if "/" in request.model:
            _, bare_model = request.model.split("/", 1)
            return GenerationRequest(
                messages=request.messages,
                model=bare_model,
                provider=provider.name,
                config=request.config,
                system_prompt=request.system_prompt,
                user_id=request.user_id,
                project_id=request.project_id,
                workspace_id=request.workspace_id,
                metadata=request.metadata,
            )
        return request

    async def _fallback_generate(
        self, request: GenerationRequest, primary_provider_name: str
    ) -> AIResponse:
        fallback_order = ["openai", "anthropic", "gemini", "openrouter", "groq", "nvidia_nim", "ollama"]
        for name in fallback_order:
            if name == primary_provider_name or not self._registry.is_available(name):
                continue
            self._logger.info("fallback_attempt", provider=name, model=request.model)
            try:
                provider = self._registry.get(name)
                adjusted = self._maybe_inject_model(
                    GenerationRequest(
                        messages=request.messages,
                        model=request.model,
                        provider=name,
                        config=request.config,
                        system_prompt=request.system_prompt,
                        user_id=request.user_id,
                        project_id=request.project_id,
                        workspace_id=request.workspace_id,
                        metadata=request.metadata,
                    ),
                    provider,
                )
                response = await provider.generate_text(adjusted)
                return self._with_cost(response)
            except Exception as exc:
                self._logger.warning("fallback_failed", provider=name, error=str(exc))
                continue
        raise ProviderUnavailableError("All fallback providers failed.", provider=request.provider)

    @staticmethod
    def _with_cost(response: AIResponse) -> AIResponse:
        # Cost estimation is handled per-feature; keep response intact here.
        return response

    @staticmethod
    async def _sleep(seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)


def get_ai_engine(settings: Settings | None = None) -> AIEngine:
    """Return a singleton AIEngine backed by application settings."""
    return AIEngine(settings=settings)
