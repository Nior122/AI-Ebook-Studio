"""Per-user AI provider preferences.

This model stores *selections* only (preferred provider/model, fallback, tuning
knobs, writing defaults). It intentionally never stores raw API keys in
plaintext. Should user-supplied keys be supported later, they must be encrypted
at rest (see ``encrypted_api_key`` / ``key_nonce`` placeholders) and the
decryption key kept outside the database.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class AIProviderPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user's AI provider configuration and writing defaults."""

    __tablename__ = "ai_provider_preferences"
    __table_args__ = (
        Index("ix_ai_provider_prefs_user_id", "user_id", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=False, unique=True
    )

    # --- provider / model selection (no secrets) ---
    preferred_provider: Mapped[str | None] = mapped_column(String(80))
    preferred_model: Mapped[str | None] = mapped_column(String(120))
    fallback_provider: Mapped[str | None] = mapped_column(String(80))
    fallback_model: Mapped[str | None] = mapped_column(String(120))

    # --- generation tuning ---
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)

    # --- writing defaults ---
    default_writing_style: Mapped[str | None] = mapped_column(String(80))
    default_language: Mapped[str | None] = mapped_column(String(40), default="en")

    # --- feature toggles ---
    stream_responses: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- encrypted key storage (unused until user-supplied keys are enabled) ---
    # When populated, ``encrypted_api_key`` holds ciphertext and ``key_nonce`` the
    # AES-GCM nonce; the KEK is provided at runtime, never persisted here.
    uses_custom_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text)
    key_nonce: Mapped[str | None] = mapped_column(Text)
    key_provider: Mapped[str | None] = mapped_column(String(40))
