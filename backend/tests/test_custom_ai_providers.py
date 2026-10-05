"""Tests for user-supplied custom AI providers (bring-your-own key/model).

Covers: encryption at rest, secret masking, CRUD validation, adapter branching,
per-user AIService registration, and the connection-test endpoint. No external
API calls are made — provider ``generate_text`` is stubbed where needed.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from core.crypto import decrypt_secret
from core.exceptions import ResourceNotFoundError, ValidationAppError
from models.accounts import User
from models.custom_ai_provider import CustomAIProvider
from schemas.ai import CustomAIProviderUpsert
from services import custom_ai_service
from services.studio_service import build_ai_service_for_user


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
async def test_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"custom_ai_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        status="active",
    )
    db_session.add(user)
    await db_session.flush()
    return user


def _payload(**overrides) -> CustomAIProviderUpsert:
    base = dict(
        name="My OpenRouter",
        provider_type="openai_compatible",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-secret-123",
        model_ids=["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
        default_model="openai/gpt-4o-mini",
    )
    base.update(overrides)
    return CustomAIProviderUpsert(**base)


async def _get_row(db_session, provider_id: uuid.UUID) -> CustomAIProvider:
    result = await db_session.execute(
        select(CustomAIProvider).where(CustomAIProvider.id == provider_id)
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# encryption at rest + masking
# ---------------------------------------------------------------------------
async def test_create_encrypts_key_at_rest(db_session, test_user):
    created = await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    assert created["has_key"] is True

    row = await _get_row(db_session, uuid.UUID(created["id"]))
    # Ciphertext must not equal the plaintext, and must decrypt back to it.
    assert row.encrypted_api_key != "sk-secret-123"
    assert "sk-secret-123" not in (row.encrypted_api_key or "")
    assert decrypt_secret(row.encrypted_api_key) == "sk-secret-123"


async def test_list_masks_key(db_session, test_user):
    await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    rows = await custom_ai_service.list_custom_providers(db_session, test_user)
    assert len(rows) == 1
    entry = rows[0]
    assert entry["has_key"] is True
    # No plaintext secret anywhere in the serialized dict.
    assert "sk-secret-123" not in str(entry)
    assert "api_key" not in entry
    assert "encrypted_api_key" not in entry


# ---------------------------------------------------------------------------
# CRUD + validation
# ---------------------------------------------------------------------------
async def test_update_keeps_key_when_omitted(db_session, test_user):
    created = await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    pk = uuid.UUID(created["id"])

    updated = await custom_ai_service.update_custom_provider(
        db_session, test_user, pk, _payload(name="Renamed", api_key=None)
    )
    assert updated["name"] == "Renamed"
    row = await _get_row(db_session, pk)
    assert decrypt_secret(row.encrypted_api_key) == "sk-secret-123"


async def test_update_replaces_key_when_supplied(db_session, test_user):
    created = await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    pk = uuid.UUID(created["id"])

    await custom_ai_service.update_custom_provider(
        db_session, test_user, pk, _payload(api_key="sk-new-999")
    )
    row = await _get_row(db_session, pk)
    assert decrypt_secret(row.encrypted_api_key) == "sk-new-999"


async def test_delete_soft_deletes_and_hides(db_session, test_user):
    created = await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    pk = uuid.UUID(created["id"])

    await custom_ai_service.delete_custom_provider(db_session, test_user, pk)
    rows = await custom_ai_service.list_custom_providers(db_session, test_user)
    assert rows == []

    row = await _get_row(db_session, pk)
    assert row.deleted_at is not None


async def test_delete_unknown_raises_not_found(db_session, test_user):
    with pytest.raises(ResourceNotFoundError):
        await custom_ai_service.delete_custom_provider(db_session, test_user, uuid.uuid4())


async def test_openai_compatible_requires_base_url(db_session, test_user):
    with pytest.raises(ValidationAppError):
        await custom_ai_service.create_custom_provider(
            db_session, test_user, _payload(base_url=None)
        )


async def test_requires_at_least_one_model(db_session, test_user):
    with pytest.raises(ValidationAppError):
        await custom_ai_service.create_custom_provider(
            db_session, test_user, _payload(model_ids=[])
        )


async def test_rejects_unknown_provider_type(db_session, test_user):
    with pytest.raises(ValidationAppError):
        await custom_ai_service.create_custom_provider(
            db_session, test_user, _payload(provider_type="carrier_pigeon")
        )


async def test_user_isolation(db_session, test_user):
    await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    other = User(
        id=uuid.uuid4(), email="other@example.com", password_hash="h", status="active"
    )
    db_session.add(other)
    await db_session.flush()
    assert await custom_ai_service.list_custom_providers(db_session, other) == []


# ---------------------------------------------------------------------------
# adapter construction + per-user AIService registration
# ---------------------------------------------------------------------------
async def test_build_instances_branch_by_type(db_session, test_user):
    from providers.ai.anthropic_provider import AnthropicProvider
    from providers.ai.custom_openai_provider import CustomOpenAIProvider
    from providers.ai.gemini_provider import GeminiProvider

    await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    await custom_ai_service.create_custom_provider(
        db_session,
        test_user,
        _payload(name="My Anthropic", provider_type="anthropic", base_url=None,
                 model_ids=["claude-3-5-sonnet-20241022"]),
    )
    await custom_ai_service.create_custom_provider(
        db_session,
        test_user,
        _payload(name="My Gemini", provider_type="gemini", base_url=None,
                 model_ids=["gemini-1.5-flash"]),
    )

    instances = await custom_ai_service.build_custom_provider_instances(db_session, test_user)
    assert len(instances) == 3
    types = {type(i) for i in instances}
    assert types == {CustomOpenAIProvider, AnthropicProvider, GeminiProvider}
    # Each instance is registered under a unique per-user provider id.
    ids = [i.name for i in instances]
    assert len(set(ids)) == 3
    assert all(i.startswith("custom-") for i in ids)


async def test_build_ai_service_registers_custom_provider(db_session, test_user):
    created = await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    service = await build_ai_service_for_user(db_session, test_user)
    assert created["provider_id"] in service._registry.list()


async def test_inactive_provider_not_registered(db_session, test_user):
    created = await custom_ai_service.create_custom_provider(
        db_session, test_user, _payload(is_active=False)
    )
    service = await build_ai_service_for_user(db_session, test_user)
    assert created["provider_id"] not in service._registry.list()


# ---------------------------------------------------------------------------
# connection test (stubbed — no network)
# ---------------------------------------------------------------------------
async def test_connection_test_success(db_session, test_user, monkeypatch):
    from providers.ai.custom_openai_provider import CustomOpenAIProvider

    async def fake_generate(self, request):
        return SimpleNamespace(content="OK")

    monkeypatch.setattr(CustomOpenAIProvider, "generate_text", fake_generate)

    created = await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    result = await custom_ai_service.test_custom_provider(
        db_session, test_user, uuid.UUID(created["id"])
    )
    assert result["ok"] is True
    assert result["model"] == "openai/gpt-4o-mini"


async def test_connection_test_failure_returns_error(db_session, test_user, monkeypatch):
    from providers.ai.custom_openai_provider import CustomOpenAIProvider

    async def fake_raise(self, request):
        raise RuntimeError("boom: invalid key")

    monkeypatch.setattr(CustomOpenAIProvider, "generate_text", fake_raise)

    created = await custom_ai_service.create_custom_provider(db_session, test_user, _payload())
    result = await custom_ai_service.test_custom_provider(
        db_session, test_user, uuid.UUID(created["id"])
    )
    assert result["ok"] is False
    assert "boom" in result["error"]
