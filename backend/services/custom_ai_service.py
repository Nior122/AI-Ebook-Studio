"""Service for user-supplied custom AI providers.

Handles CRUD for :class:`~models.custom_ai_provider.CustomAIProvider` rows,
builds live provider adapter instances (with decrypted keys) for registration in
a per-user provider registry, and runs a small connection test. API keys are
encrypted at rest via :mod:`core.crypto` and are never returned in plaintext.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.crypto import decrypt_secret, encrypt_secret
from core.exceptions import ResourceNotFoundError, ValidationAppError
from models.accounts import User
from models.custom_ai_provider import (
    CUSTOM_PROVIDER_TYPES,
    PROVIDER_TYPE_ANTHROPIC,
    PROVIDER_TYPE_GEMINI,
    PROVIDER_TYPE_OPENAI_COMPATIBLE,
    CustomAIProvider,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# serialization
# ---------------------------------------------------------------------------
def _to_dict(row: CustomAIProvider) -> dict[str, Any]:
    """Return a JSON-safe, secret-free representation of a provider row."""
    return {
        "id": str(row.id),
        "name": row.name,
        "provider_type": row.provider_type,
        "base_url": row.base_url,
        "model_ids": list(row.model_ids or []),
        "default_model": row.default_model,
        "supports_structured_output": bool(row.supports_structured_output),
        "is_active": bool(row.is_active),
        "has_key": row.has_key,
        "provider_id": row.provider_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _normalize_model_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
    elif isinstance(value, (list, tuple)):
        parts = [str(p).strip() for p in value]
    else:
        raise ValidationAppError("model_ids must be a list or comma-separated string.")
    return [p for p in parts if p]


def _validate_payload(
    data: Any, *, require_key: bool
) -> tuple[str, str, str | None, list[str], str | None, str | None]:
    """Validate an upsert payload; returns (name, type, base_url, models, default, key)."""
    name = str(getattr(data, "name", "") or "").strip()
    if not name:
        raise ValidationAppError("A provider name is required.")

    provider_type = str(getattr(data, "provider_type", "") or "").strip()
    if provider_type not in CUSTOM_PROVIDER_TYPES:
        raise ValidationAppError(
            f"Unknown provider_type '{provider_type}'. "
            f"Supported: {', '.join(CUSTOM_PROVIDER_TYPES)}"
        )

    base_url = (getattr(data, "base_url", None) or "").strip() or None
    if provider_type == PROVIDER_TYPE_OPENAI_COMPATIBLE and not base_url:
        raise ValidationAppError("OpenAI-compatible providers require a base_url.")

    model_ids = _normalize_model_ids(getattr(data, "model_ids", None))
    if not model_ids:
        raise ValidationAppError("At least one model id is required.")

    default_model = (getattr(data, "default_model", None) or "").strip() or None
    if default_model and default_model not in model_ids:
        model_ids.insert(0, default_model)

    api_key = (getattr(data, "api_key", None) or "").strip() or None
    if require_key and not api_key:
        raise ValidationAppError("An API key is required.")

    return name, provider_type, base_url, model_ids, default_model, api_key


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def list_custom_providers(
    session: AsyncSession, user: User
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(CustomAIProvider)
        .where(
            CustomAIProvider.user_id == user.id,
            CustomAIProvider.deleted_at.is_(None),
        )
        .order_by(CustomAIProvider.created_at.asc())
    )
    return [_to_dict(row) for row in result.scalars().all()]


async def _get_row(
    session: AsyncSession, user: User, provider_pk: UUID
) -> CustomAIProvider:
    result = await session.execute(
        select(CustomAIProvider).where(
            CustomAIProvider.id == provider_pk,
            CustomAIProvider.user_id == user.id,
            CustomAIProvider.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Custom AI provider not found.")
    return row


async def create_custom_provider(
    session: AsyncSession, user: User, data: Any
) -> dict[str, Any]:
    name, provider_type, base_url, model_ids, default_model, api_key = _validate_payload(
        data, require_key=False
    )
    row = CustomAIProvider(
        user_id=user.id,
        name=name,
        provider_type=provider_type,
        base_url=base_url,
        model_ids=model_ids,
        default_model=default_model or model_ids[0],
        encrypted_api_key=encrypt_secret(api_key) if api_key else None,
        supports_structured_output=bool(getattr(data, "supports_structured_output", True)),
        is_active=bool(getattr(data, "is_active", True)),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    logger.info("custom_provider_created", user=str(user.id), provider=row.provider_id)
    return _to_dict(row)


async def update_custom_provider(
    session: AsyncSession, user: User, provider_pk: UUID, data: Any
) -> dict[str, Any]:
    row = await _get_row(session, user, provider_pk)
    name, provider_type, base_url, model_ids, default_model, api_key = _validate_payload(
        data, require_key=False
    )
    row.name = name
    row.provider_type = provider_type
    row.base_url = base_url
    # JSON columns must be reassigned to mark the attribute dirty.
    row.model_ids = model_ids
    row.default_model = default_model or model_ids[0]
    if api_key:
        row.encrypted_api_key = encrypt_secret(api_key)
    if getattr(data, "supports_structured_output", None) is not None:
        row.supports_structured_output = bool(data.supports_structured_output)
    if getattr(data, "is_active", None) is not None:
        row.is_active = bool(data.is_active)
    await session.commit()
    await session.refresh(row)
    logger.info("custom_provider_updated", user=str(user.id), provider=row.provider_id)
    return _to_dict(row)


async def delete_custom_provider(
    session: AsyncSession, user: User, provider_pk: UUID
) -> None:
    row = await _get_row(session, user, provider_pk)
    from datetime import UTC, datetime

    row.deleted_at = datetime.now(UTC)
    await session.commit()
    logger.info("custom_provider_deleted", user=str(user.id), provider=row.provider_id)


# ---------------------------------------------------------------------------
# live adapter construction
# ---------------------------------------------------------------------------
def _build_instance(row: CustomAIProvider, api_key: str | None):
    """Instantiate the correct adapter for *row* under its unique provider id."""
    from providers.ai.anthropic_provider import AnthropicProvider
    from providers.ai.custom_openai_provider import CustomOpenAIProvider
    from providers.ai.gemini_provider import GeminiProvider

    if row.provider_type == PROVIDER_TYPE_ANTHROPIC:
        instance = AnthropicProvider(api_key=api_key)
    elif row.provider_type == PROVIDER_TYPE_GEMINI:
        instance = GeminiProvider(api_key=api_key)
    else:
        instance = CustomOpenAIProvider(
            api_key=api_key,
            base_url=row.base_url,
            default_model=row.default_model,
        )
    # Register under the unique per-user id so multiple custom providers (and
    # the built-in providers) can coexist in one registry without colliding.
    instance.PROVIDER = row.provider_id
    return instance


async def build_custom_provider_instances(
    session: AsyncSession, user: User
) -> list[Any]:
    """Return live adapter instances for the user's active custom providers."""
    result = await session.execute(
        select(CustomAIProvider).where(
            CustomAIProvider.user_id == user.id,
            CustomAIProvider.is_active.is_(True),
            CustomAIProvider.deleted_at.is_(None),
        )
    )
    instances: list[Any] = []
    for row in result.scalars().all():
        api_key = decrypt_secret(row.encrypted_api_key)
        try:
            instance = _build_instance(row, api_key)
            instance.validate_configuration()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "custom_provider_build_failed",
                provider=row.provider_id,
                error=str(exc),
            )
            continue
        instances.append(instance)
    return instances


async def get_provider_instance(
    session: AsyncSession, user: User, provider_pk: UUID
) -> Any:
    """Build a single adapter instance for the given provider row (for tests)."""
    row = await _get_row(session, user, provider_pk)
    api_key = decrypt_secret(row.encrypted_api_key)
    return _build_instance(row, api_key)


# ---------------------------------------------------------------------------
# connection test
# ---------------------------------------------------------------------------
async def test_custom_provider(
    session: AsyncSession, user: User, provider_pk: UUID
) -> dict[str, Any]:
    """Send a tiny completion through the provider to verify connectivity."""
    from providers.ai.base import GenerationConfig, GenerationRequest, Message

    row = await _get_row(session, user, provider_pk)
    try:
        instance = await get_provider_instance(session, user, provider_pk)
    except Exception as exc:
        return {"ok": False, "model": row.default_model, "error": str(exc)}

    model = row.default_model or (row.model_ids or [None])[0]
    request = GenerationRequest(
        messages=[Message(role="user", content="Reply with just the word OK.")],
        model=model,
        provider=row.provider_id,
        config=GenerationConfig(temperature=0.0, max_tokens=16),
    )
    try:
        response = await instance.generate_text(request)
        content = (response.content or "").strip()
        return {"ok": bool(content), "model": model, "reply": content[:120]}
    except Exception as exc:
        logger.warning("custom_provider_test_failed", provider=row.provider_id, error=str(exc))
        return {"ok": False, "model": model, "error": str(exc)}
