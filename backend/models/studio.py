"""Studio UX models — live collaboration surface for a book project.

These tables back the unified workspace experience: an activity timeline,
persistent notifications, project-level version snapshots (restore points),
and bookmarks. They hang off the project ownership chain
(User -> Workspace -> Project -> Book) and are soft-deleted like every other
entity in the platform.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.accounts import User
    from models.project import Project


class ProjectActivity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single entry in a project's live activity timeline.

    ``kind`` is a stable machine-readable label (e.g. ``chapter_generated``,
    ``image_inserted``, ``version_restored``); ``message`` is the human-readable
    line shown in the UI (e.g. "Chapter 3 generated — Foundations").
    """

    __tablename__ = "studio_activities"
    __table_args__ = (
        Index("ix_studio_activities_project_id", "project_id"),
        Index("ix_studio_activities_created_at", "project_id", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    project: Mapped[Project] = relationship()


class StudioNotification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A durable, user-scoped notification with an optional retry/action.

    ``level`` is one of ``info`` | ``success`` | ``warning`` | ``error``.
    ``action_type`` / ``action_payload`` let the UI render an actionable button
    (e.g. retry a failed job, open the project).
    """

    __tablename__ = "studio_notifications"
    __table_args__ = (
        Index("ix_studio_notifications_user_id", "user_id"),
        Index("ix_studio_notifications_project_id", "project_id"),
        Index("ix_studio_notifications_read", "user_id", "read_at"),
    )

    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_type: Mapped[str | None] = mapped_column(String(60))
    action_payload: Mapped[dict[str, object] | None] = mapped_column(JSON)

    user: Mapped[User] = relationship()


class ProjectVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A project-level restore point (full snapshot of book + settings + chapters).

    Snapshots are created automatically after major AI operations (generation,
    proofreading, formatting, translation, cover) and manually by the user.
    """

    __tablename__ = "studio_versions"
    __table_args__ = (
        Index("ix_studio_versions_project_id", "project_id"),
        Index("ix_studio_versions_created_at", "project_id", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    # Snapshot JSON: {"book": {...}, "settings": {...}, "chapters": [...]}
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)

    project: Mapped[Project] = relationship()


class Bookmark(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user bookmark pinned to a project, optionally anchored to a chapter."""

    __tablename__ = "studio_bookmarks"
    __table_args__ = (
        Index("ix_studio_bookmarks_project_id", "project_id"),
        Index("ix_studio_bookmarks_user_id", "user_id"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    chapter_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("bw_chapters.id"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship()
