"""AI generation usage record for analytics and cost tracking."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class AIUsageRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-generation telemetry row — one record for every AI.generate() call."""

    __tablename__ = "ai_usage_records"
    __table_args__ = (
        Index("ix_ai_usage_user_id", "user_id"),
        Index("ix_ai_usage_project_id", "project_id"),
        Index("ix_ai_usage_workspace_id", "workspace_id"),
        Index("ix_ai_usage_provider", "provider"),
        Index("ix_ai_usage_created_at", "created_at"),
    )

    user_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    project_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    workspace_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("workspaces.id"))

    provider: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    request_type: Mapped[str] = mapped_column(String(40), nullable=False, default="generate")

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    finish_reason: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
