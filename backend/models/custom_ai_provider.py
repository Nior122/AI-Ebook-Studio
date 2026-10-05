"""Per-user custom AI providers (bring-your-own endpoint / model / API key).

Each row is a provider the user added themselves, as opposed to the built-in
providers instantiated from server settings. Three adapter types are supported:

* ``openai_compatible`` — any OpenAI Chat-Completions endpoint (OpenRouter,
  Groq, Together, LM Studio, Ollama, vLLM, LiteLLM, …). Requires ``base_url``.
* ``anthropic`` — native Anthropic Messages API using the user's own key.
* ``gemini`` — native Google Gemini API using the user's own key.

API keys are stored Fernet-encrypted in ``encrypted_api_key`` and are never
returned in plaintext by any endpoint. The stable :attr:`provider_id` is used
to register a live adapter instance in a per-user provider registry, so saved
preferences and in-flight generation keep working across requests.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

# Adapter types a user may select for a custom provider.
PROVIDER_TYPE_OPENAI_COMPATIBLE = "openai_compatible"
PROVIDER_TYPE_ANTHROPIC = "anthropic"
PROVIDER_TYPE_GEMINI = "gemini"
CUSTOM_PROVIDER_TYPES = (
    PROVIDER_TYPE_OPENAI_COMPATIBLE,
    PROVIDER_TYPE_ANTHROPIC,
    PROVIDER_TYPE_GEMINI,
)


class CustomAIProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-supplied AI provider (endpoint + model list + encrypted key)."""

    __tablename__ = "custom_ai_providers"
    __table_args__ = (Index("ix_custom_ai_providers_user_id", "user_id"),)

    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=False
    )

    # --- identity ---
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- connection (base_url only used by openai_compatible) ---
    base_url: Mapped[str | None] = mapped_column(String(500))
    encrypted_api_key: Mapped[str | None] = mapped_column(Text)

    # --- models ---
    model_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    default_model: Mapped[str | None] = mapped_column(String(200))

    # --- capability + state ---
    supports_structured_output: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def provider_id(self) -> str:
        """Stable unique provider id used to register the live adapter."""
        return f"custom-{self.id.hex[:12]}"

    @property
    def has_key(self) -> bool:
        return bool(self.encrypted_api_key)
