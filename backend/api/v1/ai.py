"""AI Engine API endpoints — provider/model discovery, capabilities, generation.

All read/generation endpoints require authentication. Discovery endpoints
expose only configured/available providers and never expose API keys.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import AIEngineDep, AppSettings, CurrentUser, DatabaseSession
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
    CustomAIProviderSchema,
    CustomAIProviderUpsert,
)
from services.models_registry import ModelRegistry

router = APIRouter(prefix="/ai", tags=["ai"])


# -----------------------------------------------------------------------
# Discovery endpoints (authenticated)
# -----------------------------------------------------------------------
@router.get("/providers", response_model=list[ProviderSchema])
async def list_providers(
    user: CurrentUser,
    engine: AIEngineDep,
    session: DatabaseSession,
) -> list[ProviderSchema]:
    """Return configured providers plus the user's custom providers."""
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

    # Append the user's active custom providers (already keyed by the user).
    from services import custom_ai_service

    for row in await custom_ai_service.list_custom_providers(session, user):
        if not row["is_active"]:
            continue
        results.append(
            ProviderSchema(
                name=row["provider_id"],
                available=True,
                healthy=False,
                models=list(row["model_ids"]),
                requires_key=False,
            )
        )
    return results


@router.get("/models", response_model=list[ModelInfoSchema])
async def list_models(
    user: CurrentUser,
    engine: AIEngineDep,
    session: DatabaseSession,
) -> list[ModelInfoSchema]:
    """Return every built-in model plus the user's custom provider models."""
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

    # Append the user's active custom provider models.
    from services import custom_ai_service

    for row in await custom_ai_service.list_custom_providers(session, user):
        if not row["is_active"]:
            continue
        for model_id in row["model_ids"]:
            out.append(
                ModelInfoSchema(
                    key=f"{row['provider_id']}/{model_id}",
                    provider=row["provider_id"],
                    name=model_id,
                    display_name=f"{row['name']} — {model_id}",
                    context_window=None,
                    max_output_tokens=None,
                    supports_streaming=True,
                    supports_structured_output=bool(row["supports_structured_output"]),
                    supports_tools=False,
                    supports_vision=False,
                    status="active",
                    input_cost_per_1m_tokens=0.0,
                    output_cost_per_1m_tokens=0.0,
                    tags=["custom"],
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


async def _generate_with_user_service(
    session: AsyncSession,
    user: Any,
    request: GenerationRequest,
) -> AIResponse:
    """Run a generation request through the user's per-user AIService.

    This is what makes user-supplied custom providers (registered under unique
    ids by ``build_ai_service_for_user``) reachable from the direct AI endpoints.
    """
    from services.studio_service import build_ai_service_for_user

    service = await build_ai_service_for_user(session, user)
    return await service.generate_text(
        messages=request.messages,
        model=request.model,
        provider=request.provider,
        system_prompt=request.system_prompt,
        temperature=request.config.temperature,
        max_tokens=request.config.max_tokens,
        top_p=request.config.top_p,
        stream=request.config.stream,
        json_mode=request.config.json_mode,
        response_schema=request.config.response_schema,
        retry_attempts=request.config.retry_attempts,
        timeout_seconds=request.config.timeout_seconds,
        user_id=request.user_id,
        project_id=request.project_id,
        workspace_id=request.workspace_id,
        metadata=request.metadata,
    )


@router.post("/chat", response_model=GenerationResponse, status_code=status.HTTP_200_OK)
async def chat(
    payload: Annotated[ChatRequest, Body(embed=True)],
    user: CurrentUser,
    session: DatabaseSession,
    _settings: AppSettings,
) -> GenerationResponse:
    """Multi-turn chat generation (honours the user's custom providers)."""
    request = _build_request(payload, user_id=user.id)
    response = await _generate_with_user_service(session, user, request)
    await _record_usage(session, request, response, request_type="chat")
    return _to_response(response)


@router.post("/complete", response_model=GenerationResponse, status_code=status.HTTP_200_OK)
async def complete(
    payload: Annotated[CompletionRequest, Body(embed=True)],
    user: CurrentUser,
    session: DatabaseSession,
    _settings: AppSettings,
) -> GenerationResponse:
    """Single-prompt completion generation (honours custom providers)."""
    request = _build_request(payload, user_id=user.id)
    response = await _generate_with_user_service(session, user, request)
    await _record_usage(session, request, response, request_type="complete")
    return _to_response(response)


@router.post("/structured", response_model=dict, status_code=status.HTTP_200_OK)
async def structured(
    payload: Annotated[StructuredRequest, Body(embed=True)],
    user: CurrentUser,
    session: DatabaseSession,
    _settings: AppSettings,
) -> dict:
    """Generate JSON conforming to a provided schema (honours custom providers)."""
    from services.studio_service import build_ai_service_for_user

    messages = [Message(role=m.role, content=m.content) for m in payload.messages]
    service = await build_ai_service_for_user(session, user)
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
    response = await _generate_with_user_service(session, user, request)
    await _record_usage(session, request, response, request_type="test")
    return _to_response(response)


# -----------------------------------------------------------------------
# Custom (user-supplied) AI providers
# -----------------------------------------------------------------------
@router.get("/custom-providers", response_model=list[CustomAIProviderSchema])
async def list_custom_providers(
    user: CurrentUser,
    session: DatabaseSession,
) -> list[dict]:
    """List the current user's custom AI providers (keys masked)."""
    from services import custom_ai_service

    return await custom_ai_service.list_custom_providers(session, user)


@router.post(
    "/custom-providers",
    response_model=CustomAIProviderSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_provider(
    payload: Annotated[CustomAIProviderUpsert, Body(embed=True)],
    user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    """Create a custom AI provider. The API key is encrypted at rest."""
    from services import custom_ai_service

    return await custom_ai_service.create_custom_provider(session, user, payload)


@router.put("/custom-providers/{provider_pk}", response_model=CustomAIProviderSchema)
async def update_custom_provider(
    provider_pk: UUID,
    payload: Annotated[CustomAIProviderUpsert, Body(embed=True)],
    user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    """Update a custom AI provider. Omit api_key to keep the existing key."""
    from services import custom_ai_service

    return await custom_ai_service.update_custom_provider(session, user, provider_pk, payload)


@router.delete(
    "/custom-providers/{provider_pk}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_custom_provider(
    provider_pk: UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> Response:
    """Soft-delete a custom AI provider."""
    from services import custom_ai_service

    await custom_ai_service.delete_custom_provider(session, user, provider_pk)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/custom-providers/{provider_pk}/test")
async def test_custom_provider(
    provider_pk: UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    """Send a tiny completion through the provider to verify connectivity."""
    from services import custom_ai_service

    return await custom_ai_service.test_custom_provider(session, user, provider_pk)


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
