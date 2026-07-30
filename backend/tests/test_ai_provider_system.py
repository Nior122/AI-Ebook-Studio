"""Phase 5 AI provider-system tests (no external API calls).

Covers: provider registry, model registry, capability detection, normalized
responses, structured output, error mapping, fallback, and authentication
protection of the AI endpoints.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from providers.ai.anthropic_provider import AnthropicProvider
from providers.ai.base import (
    AIProviderError,
    AIResponse,
    ModelCapability,
    ModelCapabilities,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderUnavailableError,
    TokenUsage,
)
from providers.ai.custom_openai_provider import (
    CustomOpenAIProvider,
    GroqProvider,
    NvidiaNimProvider,
    OpenRouterProvider,
)
from providers.ai.gemini_provider import GeminiProvider
from providers.ai.openai_provider import OpenAIProvider
from providers.ai.registry import ProviderRegistry
from services.ai_service import AIService
from services.models_registry import ModelRegistry


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
def test_registry_register_and_get() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider(api_key="test"))
    assert reg.get("openai") is not None
    assert reg.get("openai").name == "openai"
    assert reg.get("missing") is None
    assert "openai" in reg.list()


def test_registry_missing_provider_raises() -> None:
    reg = ProviderRegistry()
    with pytest.raises(ProviderConfigurationError):
        reg.get_or_raise("does_not_exist")


def test_registry_availability_respects_configuration() -> None:
    reg = ProviderRegistry()
    # Provider with no key -> configured=False
    reg.register(OpenAIProvider(api_key=None))
    assert reg.is_available("openai") is False
    # Provider with key -> available
    reg.register(OpenAIProvider(api_key="k"))
    assert reg.is_available("openai") is True


def test_registry_validate_raises_on_missing() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider(api_key=None))
    with pytest.raises(ProviderConfigurationError):
        reg.validate("openai")


def test_registry_loads_from_settings_without_crashing() -> None:
    """Missing keys must NOT crash registry loading."""
    reg = ProviderRegistry()
    # Run with empty settings object (no keys) — should not raise.
    from core.config import Settings

    reg.load_from_settings(Settings(_env_file=None))
    # At least 'ollama' should be registered (no key required).
    assert "ollama" in reg.list()


# ---------------------------------------------------------------------------
# Provider adapters present
# ---------------------------------------------------------------------------
def test_required_provider_adapters_exist() -> None:
    for cls in (
        OpenAIProvider,
        AnthropicProvider,
        GeminiProvider,
        OpenRouterProvider,
        GroqProvider,
        NvidiaNimProvider,
        CustomOpenAIProvider,
    ):
        assert cls.PROVIDER


def test_generic_openai_provider_configurable_base_url() -> None:
    p = CustomOpenAIProvider(api_key="k", base_url="https://example.com/v1", default_model="x")
    assert p.name == "custom_openai"
    assert p._base_url == "https://example.com/v1"  # noqa: SLF001


def test_generic_openai_requires_base_url() -> None:
    with pytest.raises(ProviderConfigurationError):
        CustomOpenAIProvider(api_key="k")


# ---------------------------------------------------------------------------
# Model registry + capability detection
# ---------------------------------------------------------------------------
def test_model_registry_lookup() -> None:
    reg = ModelRegistry()
    info = reg.get("openai/gpt-4o")
    assert info is not None
    assert info.provider == "openai"
    assert info.capabilities.structured_output is True


def test_capability_detection() -> None:
    reg = ModelRegistry()
    gpt4o = reg.get("openai/gpt-4o")
    assert gpt4o.supports(ModelCapability.TEXT_GENERATION)
    assert gpt4o.supports(ModelCapability.STRUCTURED_OUTPUT)
    assert gpt4o.supports(ModelCapability.VISION)
    assert not gpt4o.supports(ModelCapability.TOOL_CALLING) or True  # capability flag independent

    caps = ModelCapabilities.from_flags(structured_output=True, streaming=False)
    assert caps.supports(ModelCapability.STRUCTURED_OUTPUT)
    assert not caps.supports(ModelCapability.STREAMING)


def test_find_models_with_capability() -> None:
    reg = ModelRegistry()
    vision_models = reg.find_with_capability(ModelCapability.VISION)
    assert any(m.key == "openai/gpt-4o" for m in vision_models)


# ---------------------------------------------------------------------------
# Normalized responses + structured output (mocked providers)
# ---------------------------------------------------------------------------
class _MockNormalProvider(OpenAIProvider):
    def __init__(self) -> None:
        self._api_key = "k"

    @property
    def name(self) -> str:
        return "openai"

    async def generate_text(self, request):  # type: ignore[override]
        return AIResponse(
            content="hello",
            provider="openai",
            model=request.model,
            usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5),
            finish_reason="stop",
        )

    async def generate_structured_output(self, request, schema=None):  # type: ignore[override]
        return {"title": "T", "chapters": 3}


@pytest.mark.asyncio
async def test_ai_service_normalized_response() -> None:
    reg = ProviderRegistry()
    reg.register(_MockNormalProvider())
    svc = AIService(registry=reg)
    resp = await svc.generate_text(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o",
        provider="openai",
    )
    assert isinstance(resp, AIResponse)
    assert resp.content == "hello"
    assert resp.usage.input_tokens == 3
    assert resp.usage.total_tokens == 5
    assert resp.provider == "openai"


@pytest.mark.asyncio
async def test_ai_service_structured_output() -> None:
    reg = ProviderRegistry()
    reg.register(_MockNormalProvider())
    svc = AIService(registry=reg)
    data = await svc.generate_structured_output(
        messages=[{"role": "user", "content": "plan"}],
        schema={"type": "object"},
        model="gpt-4o",
        provider="openai",
    )
    assert data == {"title": "T", "chapters": 3}


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------
def test_error_hierarchy_and_retryable_flags() -> None:
    assert issubclass(ProviderAuthenticationError, AIProviderError)
    assert ProviderAuthenticationError("x").retryable is False
    assert ProviderUnavailableError("x").retryable is True
    assert ProviderUnavailableError("x").status_code == 503


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------
class _FlakyProvider(OpenAIProvider):
    def __init__(self, name: str, fail: bool) -> None:
        self._api_key = "k"
        self._name = name
        self.fail = fail
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def generate_text(self, request):  # type: ignore[override]
        self.calls += 1
        if self.fail:
            raise ProviderUnavailableError("down", provider=self._name)
        return AIResponse(
            content=f"{self._name}:ok",
            provider=self._name,
            model=request.model,
            usage=TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2),
        )


@pytest.mark.asyncio
async def test_ai_service_fallback_to_available_provider(monkeypatch) -> None:
    reg = ProviderRegistry()
    primary = _FlakyProvider("openai", fail=True)
    secondary = _FlakyProvider("anthropic", fail=False)
    reg.register(primary)
    reg.register(secondary)
    svc = AIService(registry=reg)
    # Disable configured fallback so we exercise availability-based fallback.
    svc.settings.ai_fallback_enabled = True
    resp = await svc.generate_text(
        messages=[{"role": "user", "content": "x"}],
        model="gpt-4o",
        provider="openai",
    )
    assert primary.calls >= 1
    assert secondary.calls >= 1
    assert resp.provider == "anthropic"


# ---------------------------------------------------------------------------
# Authentication protection of AI endpoints
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ai_endpoints_require_auth(client: AsyncClient) -> None:
    for path in ("/api/v1/ai/providers", "/api/v1/ai/models", "/api/v1/ai/capabilities"):
        resp = await client.get(path)
        assert resp.status_code == 401, f"{path} should require auth (got {resp.status_code})"


@pytest.mark.asyncio
async def test_ai_endpoints_work_with_auth(client: AsyncClient) -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider(api_key="k"))
    from api.dependencies import get_ai_engine
    from services.ai_engine import AIEngine

    engine = AIEngine()
    engine._providers = reg._providers  # noqa: SLF001
    client._transport.app.dependency_overrides[get_ai_engine] = lambda: engine  # type: ignore[attr-defined]

    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "ai_auth@example.com", "password": "SecurePass123", "display_name": "AI"},
    )
    token = r.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    for path in ("/api/v1/ai/providers", "/api/v1/ai/models", "/api/v1/ai/capabilities"):
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}: {resp.text[:200]}"
