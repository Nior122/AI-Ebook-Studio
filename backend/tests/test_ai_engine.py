"""AI engine tests with mocked providers."""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from providers.ai.base import (
    AIError,
    AIProvider,
    GenerationRequest,
    AIResponse,
    TokenUsage,
)
from services.ai_engine import AIEngine, get_ai_engine


class MockProvider(AIProvider):
    """Deterministic provider for engine and API tests."""

    def __init__(self, name: str, *, fail: bool = False) -> None:
        self._name = name
        self.fail = fail
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def health_check(self) -> bool:
        return not self.fail

    async def generate_text(self, request: GenerationRequest) -> AIResponse:
        self.calls += 1
        if self.fail:
            raise AIError("mock failure", provider=self.name, retryable=True)
        return AIResponse(
            content=f"{self.name}:{request.model}",
            finish_reason="stop",
            provider=self.name,
            model=request.model,
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            metadata={},
        )

    async def stream_text(self, request: GenerationRequest) -> AsyncIterator[str]:
        yield "hello"
        yield " "
        yield request.model

    async def count_tokens(self, text: str, model: str) -> int:
        return max(1, len(text) // 4)

    async def get_available_models(self) -> list[str]:
        return ["gpt-4o-mini", "claude-3-5-haiku-20241022"]


def build_engine() -> AIEngine:
    """Create an engine with deterministic mocked providers."""
    engine = AIEngine()
    engine._providers = {  # noqa: SLF001
        "openai": MockProvider("openai"),
        "anthropic": MockProvider("anthropic"),
    }
    return engine


@pytest.mark.asyncio
async def test_provider_switching_and_generation() -> None:
    """The engine routes by provider/model prefix."""
    engine = build_engine()
    request = GenerationRequest(messages=[], model="anthropic/claude-3-5-haiku-20241022")

    response = await engine.generate(request)

    assert response.provider == "anthropic"
    assert response.model == "claude-3-5-haiku-20241022"
    assert response.usage.total_tokens == 15


@pytest.mark.asyncio
async def test_fallback_provider_is_used_after_retryable_failure() -> None:
    """A retryable provider failure cascades to the next configured provider."""
    engine = AIEngine()
    openai = MockProvider("openai", fail=True)
    anthropic = MockProvider("anthropic")
    engine._providers = {"openai": openai, "anthropic": anthropic}  # noqa: SLF001
    request = GenerationRequest(messages=[], model="openai/gpt-4o-mini")

    response = await engine.generate(request)

    assert openai.calls == 1
    assert anthropic.calls == 1
    assert response.provider == "anthropic"


@pytest.mark.asyncio
async def test_streaming_yields_provider_chunks() -> None:
    """Streaming uses provider stream_text chunks."""
    engine = build_engine()
    request = GenerationRequest(messages=[], model="openai/gpt-4o-mini")

    chunks = [chunk async for chunk in engine.stream(request)]

    assert chunks == ["hello", " ", "gpt-4o-mini"]


@pytest.mark.asyncio
async def test_ai_status_and_completion_endpoint(client: AsyncClient) -> None:
    """AI endpoints expose health and use the mocked engine for completions."""
    engine = build_engine()

    async def override_engine() -> AIEngine:
        return engine

    client._transport.app.dependency_overrides[get_ai_engine] = override_engine  # type: ignore[attr-defined]  # noqa: SLF001

    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ai-endpoint@example.com",
            "password": "SecurePass123",
            "display_name": "AI Endpoint",
        },
    )
    token = registration.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    status_response = await client.get("/api/v1/ai/status", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["overall"] == "ok"

    models_response = await client.get("/api/v1/ai/models", headers=headers)
    assert models_response.status_code == 200
    assert any(model["provider"] == "openai" for model in models_response.json())

    completion = await client.post(
        "/api/v1/ai/complete",
        json={"payload": {"prompt": "Say OK", "model": "openai/gpt-4o-mini"}},
        headers=headers,
    )

    assert completion.status_code == 200, completion.text
    body = completion.json()
    assert body["provider"] == "openai"
    assert body["usage"]["total_tokens"] == 15
