"""Operational activity, notification, job, and audit models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class ActivityLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-visible project and workspace activity history."""

    __tablename__ = "activity_logs"
    __table_args__ = (
        Index("ix_activity_logs_workspace_id", "workspace_id"),
        Index("ix_activity_logs_project_id", "project_id"),
        Index("ix_activity_logs_actor_user_id", "actor_user_id"),
    )

    workspace_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("workspaces.id"))
    project_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    actor_user_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-facing notification."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_read_at", "read_at"),
    )

    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("workspaces.id"))
    project_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persistent async job record.

    Designed for future background workers. ``payload``/``result`` are retained
    for backward compatibility with earlier stages; Phase 3 adds richer
    progress/lifecycle tracking (``book_id``, ``progress``, ``current_step``,
    ``result_data``, ``started_at``, ``completed_at``).
    """

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_user_id", "user_id"),
        Index("ix_jobs_workspace_id", "workspace_id"),
        Index("ix_jobs_project_id", "project_id"),
        Index("ix_jobs_book_id", "book_id"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_job_type", "job_type"),
    )

    user_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    workspace_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("workspaces.id"))
    project_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    book_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("books.id"))
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(200))
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict[str, object] | None] = mapped_column(JSON)
    result_data: Mapped[dict[str, object] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Security and compliance audit trail."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_workspace_id", "workspace_id"),
        Index("ix_audit_logs_project_id", "project_id"),
        Index("ix_audit_logs_action", "action"),
    )

    user_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    workspace_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("workspaces.id"))
    project_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[UUID | None] = mapped_column(GUID())
    ip_address: Mapped[str | None] = mapped_column(String(80))
    user_agent: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
