"""Central AI service — the only entry point application features should use.

Features (writing engine, analyzer, image planner, …) call ``AIService`` rather
than touching a provider directly::

    ai_service = AIService()
    response = await ai_service.generate_text(
        task="write_chapter",
        messages=messages,
        provider="openrouter",
        model="openai/gpt-4o",
    )

The service:
1. Resolves the provider (explicit id or ``provider/model`` string).
2. Resolves the concrete model name.
3. Validates required capabilities against the model registry.
4. Executes the request with retry + fallback.
5. Normalizes the response into :class:`AIResponse`.
6. Records useful metadata (provider, model, latency, task).
7. Normalizes provider errors into the typed :mod:`providers.ai.base` errors.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import structlog

from core.config import Settings, get_settings
from providers.ai.base import (
    AIProvider,
    AIProviderError,
    AIResponse,
    ModelCapability,
    ModelNotFoundError,
    ProviderConfigurationError,
    UnsupportedCapabilityError,
)
from providers.ai.registry import ProviderRegistry
from services.models_registry import ModelRegistry

logger = structlog.get_logger(__name__)


class AIService:
    """Provider-agnostic AI orchestration layer."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        registry: ProviderRegistry | None = None,
        model_registry: ModelRegistry | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._registry = registry or ProviderRegistry()
        self._model_registry = model_registry or ModelRegistry()
        if not self._registry.list():
            self._registry.load_from_settings(self.settings)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    async def generate_text(
        self,
        *,
        messages: list[Any],
        model: str | None = None,
        provider: str | None = None,
        task: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stream: bool = False,
        json_mode: bool = False,
        response_schema: dict[str, Any] | None = None,
        required_capabilities: list[ModelCapability] | None = None,
        retry_attempts: int = 0,
        timeout_seconds: float = 120.0,
        user_id: Any | None = None,
        project_id: Any | None = None,
        workspace_id: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AIResponse:
        """Generate text, resolving provider/model and applying fallback."""
        resolved_model, resolved_provider = self._resolve(model, provider)

        capability_reqs = required_capabilities or (
            [ModelCapability.TEXT_GENERATION] if not json_mode else [ModelCapability.STRUCTURED_OUTPUT]
        )
        self._validate_capabilities(resolved_model, resolved_provider, capability_reqs)

        from providers.ai.base import GenerationConfig, GenerationRequest, Message

        request = GenerationRequest(
            messages=[m if isinstance(m, Message) else Message(**m) for m in messages],
            model=resolved_model,
            provider=resolved_provider,
            config=GenerationConfig(
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=stream,
                json_mode=json_mode,
                response_schema=response_schema,
                retry_attempts=retry_attempts,
                timeout_seconds=timeout_seconds,
            ),
            system_prompt=system_prompt,
            user_id=user_id,
            project_id=project_id,
            workspace_id=workspace_id,
            metadata={"task": task, **(metadata or {})},
        )

        return await self._execute_with_fallback(
            request, primary_provider=resolved_provider, task=task
        )

    async def generate_structured_output(
        self,
        *,
        messages: list[Any],
        schema: dict[str, Any],
        model: str | None = None,
        provider: str | None = None,
        task: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        required_capabilities: list[ModelCapability] | None = None,
        retry_attempts: int = 0,
        user_id: Any | None = None,
        project_id: Any | None = None,
        workspace_id: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return JSON conforming to *schema*."""
        resolved_model, resolved_provider = self._resolve(model, provider)
        self._validate_capabilities(
            resolved_model,
            resolved_provider,
            required_capabilities or [ModelCapability.STRUCTURED_OUTPUT],
        )

        from providers.ai.base import GenerationConfig, GenerationRequest, Message

        request = GenerationRequest(
            messages=[m if isinstance(m, Message) else Message(**m) for m in messages],
            model=resolved_model,
            provider=resolved_provider,
            config=GenerationConfig(
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
                response_schema=schema,
                retry_attempts=retry_attempts,
            ),
            system_prompt=system_prompt,
            user_id=user_id,
            project_id=project_id,
            workspace_id=workspace_id,
            metadata={"task": task, **(metadata or {})},
        )
        provider_obj = self._registry.get_or_raise(resolved_provider)
        attempts = max(1, retry_attempts + 1)
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                return await provider_obj.generate_structured_output(request, schema)
            except AIProviderError as exc:
                last_exc = exc
                if not exc.retryable:
                    break
        if last_exc:
            raise last_exc
        raise ProviderConfigurationError("Structured generation failed.", provider=resolved_provider)

    async def stream_text(
        self,
        *,
        messages: list[Any],
        model: str | None = None,
        provider: str | None = None,
        task: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float | None = None,
        user_id: Any | None = None,
        project_id: Any | None = None,
        workspace_id: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Yield text chunks. Falls back to a single buffered chunk on failure."""
        from providers.ai.base import GenerationConfig, GenerationRequest, Message

        resolved_model, resolved_provider = self._resolve(model, provider)
        self._validate_capabilities(
            resolved_model, resolved_provider, [ModelCapability.STREAMING], soft=True
        )
        provider_obj = self._registry.get_or_raise(resolved_provider)
        request = GenerationRequest(
            messages=[m if isinstance(m, Message) else Message(**m) for m in messages],
            model=resolved_model,
            provider=resolved_provider,
            config=GenerationConfig(
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=True,
            ),
            system_prompt=system_prompt,
            user_id=user_id,
            project_id=project_id,
            workspace_id=workspace_id,
            metadata={"task": task, **(metadata or {})},
        )
        try:
            async for chunk in provider_obj.stream_text(request):
                yield chunk
        except NotImplementedError:
            response = await provider_obj.generate_text(request)
            yield response.content

    # ------------------------------------------------------------------
    # resolution + validation
    # ------------------------------------------------------------------
    def _resolve(self, model: str | None, provider: str | None) -> tuple[str, str]:
        """Return (model_name, provider_id)."""
        if model and "/" in model:
            provider_id, model_name = model.split("/", 1)
            return model_name, provider_id
        if provider and model:
            return model, provider
        # fall back to configured defaults
        default = self.settings.ai_default_model
        if default and "/" in default:
            pid, mname = default.split("/", 1)
            return mname, pid
        if self._registry.list():
            return (model or "default"), self._registry.list()[0]
        raise ProviderConfigurationError("No AI provider is configured.")

    def _validate_capabilities(
        self,
        model_name: str,
        provider_id: str,
        capabilities: list[ModelCapability],
        soft: bool = False,
    ) -> None:
        info = self._model_registry.get(f"{provider_id}/{model_name}") or self._model_registry.get(
            model_name
        )
        if info is None:
            # Unknown model — do not block (provider may supply it dynamically).
            return
        missing = [c for c in capabilities if not info.supports(c)]
        if missing and not soft:
            labels = ", ".join(c.value for c in missing)
            raise UnsupportedCapabilityError(
                f"Model {provider_id}/{model_name} does not support: {labels}.",
                provider=provider_id,
                model=model_name,
            )

    # ------------------------------------------------------------------
    # execution with retry + fallback
    # ------------------------------------------------------------------
    async def _execute_with_fallback(
        self,
        request: Any,
        *,
        primary_provider: str,
        task: str | None = None,
    ) -> AIResponse:
        provider_obj = self._registry.get_or_raise(primary_provider)
        attempts = max(1, request.config.retry_attempts + 1)
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = await provider_obj.generate_text(request)
                return self._annotate(response, task)
            except AIProviderError as exc:
                last_exc = exc
                if not exc.retryable:
                    break
                logger.warning(
                    "generation_retry",
                    provider=primary_provider,
                    model=request.model,
                    attempt=attempt,
                    error=str(exc),
                )
                await self._sleep(0.5 * attempt)

        if self.settings.ai_fallback_enabled:
            fallback_response = await self._fallback(request, primary_provider, task)
            if fallback_response is not None:
                return fallback_response

        if last_exc:
            raise last_exc
        raise ProviderConfigurationError("Generation failed with no provider.", provider=primary_provider)

    async def _fallback(
        self, request: Any, primary_provider: str, task: str | None
    ) -> AIResponse | None:
        """Try the configured/next available provider."""
        order: list[str] = []
        if self.settings.ai_fallback_provider and self.settings.ai_fallback_provider != primary_provider:
            order.append(self.settings.ai_fallback_provider)
        order += [p for p in self._registry.available() if p != primary_provider]

        for pid in order:
            provider_obj = self._registry.get(pid)
            if provider_obj is None:
                continue
            # Re-point the request to this provider's model namespace.
            adjusted = self._repoint(request, pid)
            try:
                logger.info("fallback_attempt", provider=pid, model=adjusted.model)
                response = await provider_obj.generate_text(adjusted)
                return self._annotate(response, task)
            except AIProviderError as exc:
                logger.warning("fallback_failed", provider=pid, error=str(exc))
                continue
        return None

    @staticmethod
    def _repoint(request: Any, provider_id: str) -> Any:
        # Keep the same bare model name; the new provider resolves it.
        return type(request)(
            messages=request.messages,
            model=request.model,
            provider=provider_id,
            config=request.config,
            system_prompt=request.system_prompt,
            user_id=request.user_id,
            project_id=request.project_id,
            workspace_id=request.workspace_id,
            metadata=request.metadata,
        )

    @staticmethod
    def _annotate(response: AIResponse, task: str | None) -> AIResponse:
        metadata = dict(response.metadata)
        if task:
            metadata["task"] = task
        return AIResponse(
            content=response.content,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
            finish_reason=response.finish_reason,
            metadata=metadata,
        )

    @staticmethod
    async def _sleep(seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    async def health(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for pid, provider in self._registry._providers.items():  # noqa: SLF001
            try:
                result[pid] = await provider.health_check()
            except Exception:
                result[pid] = False
        return result

    @property
    def available_providers(self) -> list[str]:
        return self._registry.available()


# lazy singleton
def get_ai_service(settings: Settings | None = None) -> AIService:
    """Return a singleton :class:`AIService` backed by application settings."""
    return AIService(settings=settings)
