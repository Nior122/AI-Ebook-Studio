"""Provider registry — the single source of truth for configured providers.

The registry is intentionally decoupled from the engine. It knows how to
instantiate each built-in provider from application settings, keeps a live
instance per provider id, and exposes availability / validation helpers.
"""

from __future__ import annotations

import structlog
from typing import Callable

from core.config import Settings, get_settings
from providers.ai.anthropic_provider import AnthropicProvider
from providers.ai.base import AIProvider, AIProviderError, ProviderConfigurationError
from providers.ai.custom_openai_provider import (
    CustomOpenAIProvider,
    GroqProvider,
    NvidiaNimProvider,
    OpenRouterProvider,
)
from providers.ai.gemini_provider import GeminiProvider
from providers.ai.ollama_provider import OllamaProvider
from providers.ai.openai_provider import OpenAIProvider

logger = structlog.get_logger(__name__)


class ProviderRegistry:
    """Register, retrieve, and validate AI providers."""

    # Factory map: provider id -> (cls, kwargs-extractor from settings).
    _BUILTIN: dict[str, type[AIProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
        "groq": GroqProvider,
        "nvidia_nim": NvidiaNimProvider,
        "custom_openai": CustomOpenAIProvider,
        "ollama": OllamaProvider,
    }

    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}
        self._factories: dict[str, Callable[[Settings], AIProvider | None]] = {}

    # ------------------------------------------------------------------
    # registration
    # ------------------------------------------------------------------
    def register(self, provider: AIProvider) -> None:
        """Register a live provider instance under its ``name``."""
        self._providers[provider.name] = provider

    def register_factory(self, provider_id: str, factory: Callable[[], AIProvider | None]) -> None:
        """Register a deferred factory (e.g. for user-supplied providers)."""
        self._factories[provider_id] = factory  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # retrieval
    # ------------------------------------------------------------------
    def get(self, provider_id: str) -> AIProvider | None:
        return self._providers.get(provider_id)

    def get_or_raise(self, provider_id: str) -> AIProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise ProviderConfigurationError(
                f"Provider '{provider_id}' is not configured.", provider=provider_id
            )
        return provider

    def list(self) -> list[str]:
        return sorted(self._providers.keys())

    def available(self) -> list[str]:
        """Return ids of providers that pass configuration validation."""
        result: list[str] = []
        for pid, provider in self._providers.items():
            try:
                provider.validate_configuration()
            except AIProviderError:
                continue
            result.append(pid)
        return result

    def is_available(self, provider_id: str) -> bool:
        provider = self._providers.get(provider_id)
        if provider is None:
            return False
        try:
            provider.validate_configuration()
        except AIProviderError:
            return False
        return True

    def validate(self, provider_id: str) -> None:
        """Raise :class:`ProviderConfigurationError` if not configured."""
        provider = self._providers.get(provider_id)
        if provider is None:
            raise ProviderConfigurationError(
                f"Provider '{provider_id}' is not registered.", provider=provider_id
            )
        provider.validate_configuration()

    # ------------------------------------------------------------------
    # auto-discovery from settings
    # ------------------------------------------------------------------
    def load_from_settings(self, settings: Settings | None = None) -> None:
        """Instantiate every built-in provider whose config is present.

        Missing keys are *not* an error — the provider is simply skipped so the
        application keeps running with only the providers it has credentials for.
        """
        settings = settings or get_settings()
        builders: dict[str, Callable[[], AIProvider | None]] = {
            "openai": lambda: OpenAIProvider(api_key=settings.openai_api_key),
            "anthropic": lambda: AnthropicProvider(api_key=settings.anthropic_api_key),
            "gemini": lambda: GeminiProvider(api_key=settings.resolved_google_api_key),
            "openrouter": lambda: OpenRouterProvider(api_key=settings.openrouter_api_key),
            "groq": lambda: GroqProvider(api_key=settings.groq_api_key),
            "nvidia_nim": lambda: NvidiaNimProvider(api_key=settings.nvidia_nim_api_key),
            "custom_openai": lambda: (
                CustomOpenAIProvider(
                    api_key=settings.custom_openai_api_key,
                    base_url=settings.custom_openai_base_url,
                    default_model=settings.custom_openai_model,
                )
                if settings.custom_openai_base_url
                else None
            ),
            "ollama": lambda: OllamaProvider(base_url=settings.ollama_base_url),
        }
        for pid, builder in builders.items():
            try:
                provider = builder()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("provider_build_failed", provider=pid, error=str(exc))
                continue
            if provider is None:
                continue
            try:
                provider.validate_configuration()
            except ProviderConfigurationError:
                # Not configured — register lazily but mark unavailable.
                # We still register so capability/health endpoints can report it.
                self._providers[pid] = provider
                logger.debug("provider_unconfigured", provider=pid)
                continue
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("provider_validate_failed", provider=pid, error=str(exc))
                self._providers[pid] = provider
                continue
            self._providers[pid] = provider
            logger.debug("provider_initialized", provider=pid)


# module-level singleton
registry = ProviderRegistry()
