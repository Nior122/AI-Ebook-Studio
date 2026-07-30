"""AI Engine API endpoints — provider/model discovery, capabilities, generation.

All read/generation endpoints require authentication. Discovery endpoints
expose only configured/available providers and never expose API keys.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import AIEngineDep, AppSettings, CurrentUser, DatabaseSession, get_ai_service
from models.ai_usage import AIUsageRecord
from providers.ai.base import (
    AIResponse,
    GenerationConfig,
    GenerationRequest,
    Message,
    ModelCapability,
)
from schemas.ai import (
    ChatMessage,
    ChatRequest,
    CompletionRequest,
    GenerationResponse,
    HealthStatus,
    ModelInfoSchema,
    ProviderSchema,
    CapabilitiesSchema,
    StructuredRequest,
    AIProviderPreferenceSchema,
)
from services.ai_service import AIService
from services.models_registry import ModelRegistry

router = APIRouter(prefix="/ai", tags=["ai"])


# -----------------------------------------------------------------------
# Discovery endpoints (authenticated)
# -----------------------------------------------------------------------
@router.get("/providers", response_model=list[ProviderSchema])
async def list_providers(
    _user: CurrentUser,
    engine: AIEngineDep,
) -> list[ProviderSchema]:
    """Return configured providers with availability and model names."""
    results: list[ProviderSchema] = []
    for name in engine.available_providers:
        models = ModelRegistry().by_provider(name)
        healthy = await engine.health(name)
        results.append(
            ProviderSchema(
                name=name,
                available=True,
                healthy=healthy.get(name, False),
                models=[m.name for m in models],
                requires_key=name not in ("ollama",),
            )
        )
    return results


@router.get("/models", response_model=list[ModelInfoSchema])
async def list_models(
    _user: CurrentUser,
    engine: AIEngineDep,
) -> list[ModelInfoSchema]:
    """Return every model registered across configured providers."""
    registry = ModelRegistry()
    out: list[ModelInfoSchema] = []
    for info in registry.models.values():
        if info.provider not in engine.available_providers:
            continue
        out.append(
            ModelInfoSchema(
                key=info.key,
                provider=info.provider,
                name=info.name,
                display_name=info.name,
                context_window=info.context_length,
                max_output_tokens=info.max_output_tokens,
                supports_streaming=info.supports_streaming,
                supports_structured_output=info.supports_json_mode,
                supports_tools=info.supports_tools,
                supports_vision=info.supports_images,
                status=info.status,
                input_cost_per_1m_tokens=info.input_cost_per_1m_tokens,
                output_cost_per_1m_tokens=info.output_cost_per_1m_tokens,
                tags=list(info.tags),
            )
        )
    return out


@router.get("/capabilities", response_model=list[CapabilitiesSchema])
async def list_capabilities(
    _user: CurrentUser,
    engine: AIEngineDep,
) -> list[CapabilitiesSchema]:
    """Return capability matrix for every available model.

    Lets the frontend build capability-aware UI (e.g. disable structured-output
    features for models that don't support it).
    """
    registry = ModelRegistry()
    out: list[CapabilitiesSchema] = []
    for info in registry.models.values():
        if info.provider not in engine.available_providers:
            continue
        caps = info.capabilities.to_dict()
        out.append(
            CapabilitiesSchema(
                key=info.key,
                provider=info.provider,
                name=info.name,
                capabilities=caps,
                context_window=info.context_length,
            )
        )
    return out


# -----------------------------------------------------------------------
# System status (authenticated)
# -----------------------------------------------------------------------
@router.get("/status", response_model=HealthStatus)
async def get_ai_status(_user: CurrentUser, engine: AIEngineDep) -> HealthStatus:
    """Return health status for all configured providers."""
    health = await engine.health()
    available = sum(1 for v in health.values() if v)
    total = len(health)
    if total == 0:
        overall = "unavailable"
    elif available == total:
        overall = "ok"
    else:
        overall = "degraded"
    return HealthStatus(
        overall=overall,
        providers=health,
        timestamp=datetime.now(UTC),
    )


# -----------------------------------------------------------------------
# Generation endpoints (authenticated)
# -----------------------------------------------------------------------
def _build_request(
    payload: ChatRequest | CompletionRequest,
    *,
    user_id: UUID | None = None,
) -> GenerationRequest:
    """Normalise a chat or completion payload into a canonical GenerationRequest."""
    config_data = payload.config.model_dump()
    config = GenerationConfig(**config_data)

    if isinstance(payload, CompletionRequest):
        messages = [Message(role="user", content=payload.prompt)]
        provider = payload.provider
    else:
        messages = [Message(role=m.role, content=m.content) for m in payload.messages]
        provider = payload.provider

    resolved_model = payload.model or "openai/gpt-4o-mini"

    return GenerationRequest(
        messages=messages,
        model=resolved_model,
        provider=provider,
        config=config,
        system_prompt=payload.system_prompt,
        user_id=user_id,
    )


def _to_response(response: AIResponse) -> GenerationResponse:
    return GenerationResponse(
        content=response.content,
        provider=response.provider,
        model=response.model,
        finish_reason=response.finish_reason,
        usage={
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.total_tokens,
            "estimated_cost_usd": response.metadata.get("estimated_cost_usd", 0.0),
        },
        latency_ms=response.metadata.get("latency_ms", 0.0),
    )


async def _record_usage(
    session: AsyncSession,
    request: GenerationRequest,
    response: AIResponse,
    *,
    request_type: str,
) -> None:
    session.add(
        AIUsageRecord(
            user_id=request.user_id,
            project_id=request.project_id,
            workspace_id=request.workspace_id,
            provider=response.provider,
            model=response.model,
            request_type=request_type,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
            estimated_cost_usd=response.metadata.get("estimated_cost_usd", 0.0),
            latency_ms=response.metadata.get("latency_ms", 0.0),
            finish_reason=response.finish_reason,
        )
    )
    await session.commit()


@router.post("/chat", response_model=GenerationResponse, status_code=status.HTTP_200_OK)
async def chat(
    payload: Annotated[ChatRequest, Body(embed=True)],
    engine: AIEngineDep,
    user: CurrentUser,
    session: DatabaseSession,
    _settings: AppSettings,
) -> GenerationResponse:
    """Multi-turn chat generation."""
    request = _build_request(payload, user_id=user.id)
    response = await engine.generate(request)
    await _record_usage(session, request, response, request_type="chat")
    return _to_response(response)


@router.post("/complete", response_model=GenerationResponse, status_code=status.HTTP_200_OK)
async def complete(
    payload: Annotated[CompletionRequest, Body(embed=True)],
    engine: AIEngineDep,
    user: CurrentUser,
    session: DatabaseSession,
    _settings: AppSettings,
) -> GenerationResponse:
    """Single-prompt completion generation."""
    request = _build_request(payload, user_id=user.id)
    response = await engine.generate(request)
    await _record_usage(session, request, response, request_type="complete")
    return _to_response(response)


@router.post("/structured", response_model=dict, status_code=status.HTTP_200_OK)
async def structured(
    payload: Annotated[StructuredRequest, Body(embed=True)],
    service: Annotated[AIService, Depends(get_ai_service)],
    user: CurrentUser,
    _settings: AppSettings,
) -> dict:
    """Generate JSON conforming to a provided schema."""
    messages = [Message(role=m.role, content=m.content) for m in payload.messages]
    result = await service.generate_structured_output(
        messages=messages,
        schema=payload.response_schema,
        model=payload.model,
        provider=payload.provider,
        system_prompt=payload.system_prompt,
        task=payload.task,
        user_id=user.id,
    )
    return result


@router.post("/test", response_model=GenerationResponse, status_code=status.HTTP_200_OK)
async def test_generation(
    engine: AIEngineDep,
    user: CurrentUser,
    session: DatabaseSession,
) -> GenerationResponse:
    """Quick test: send 'Hello' to the default provider and return the reply."""
    payload = ChatRequest(
        messages=[
            {
                "role": "user",
                "content": "Hello, can you confirm you're working? Reply with just 'OK'.",
            }
        ],
        model="openai/gpt-4o-mini",
    )
    request = _build_request(payload, user_id=user.id)
    response = await engine.generate(request)
    await _record_usage(session, request, response, request_type="test")
    return _to_response(response)


# -----------------------------------------------------------------------
# User AI preferences (selections only; never persists raw API keys)
# -----------------------------------------------------------------------
@router.get("/preferences")
async def get_preferences(
    user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    """Return the current user's AI provider preferences (no secrets)."""
    from models.ai_provider_config import AIProviderPreference
    from sqlalchemy import select

    result = await session.execute(
        select(AIProviderPreference).where(AIProviderPreference.user_id == user.id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        return AIProviderPreferenceSchema().model_dump(mode="json")
    return _pref_to_dict(pref)


@router.put("/preferences", status_code=status.HTTP_200_OK)
async def update_preferences(
    payload: Annotated[AIProviderPreferenceSchema, Body(embed=True)],
    user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    """Create or update the current user's AI provider preferences."""
    from models.ai_provider_config import AIProviderPreference
    from sqlalchemy import select

    result = await session.execute(
        select(AIProviderPreference).where(AIProviderPreference.user_id == user.id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = AIProviderPreference(user_id=user.id)
        session.add(pref)
    for field_name in (
        "preferred_provider",
        "preferred_model",
        "fallback_provider",
        "fallback_model",
        "temperature",
        "default_writing_style",
        "default_language",
        "stream_responses",
    ):
        setattr(pref, field_name, getattr(payload, field_name))
    await session.commit()
    await session.refresh(pref)
    return _pref_to_dict(pref)


def _pref_to_dict(pref: object) -> dict:
    """Build a JSON-safe dict from an AIProviderPreference row."""
    return {
        "preferred_provider": getattr(pref, "preferred_provider", None),
        "preferred_model": getattr(pref, "preferred_model", None),
        "fallback_provider": getattr(pref, "fallback_provider", None),
        "fallback_model": getattr(pref, "fallback_model", None),
        "temperature": float(getattr(pref, "temperature", 0.7)),
        "default_writing_style": getattr(pref, "default_writing_style", None),
        "default_language": getattr(pref, "default_language", "en"),
        "stream_responses": bool(getattr(pref, "stream_responses", True)),
    }
