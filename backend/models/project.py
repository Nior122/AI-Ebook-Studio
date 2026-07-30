"""Project, book, folder, and settings models."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.assets import (
        BookSettings,
        DocumentAsset,
        ImageAsset,
        KDPValidationReport,
        MarketingAsset,
        TranslationRecord,
    )
    from models.document import Chapter, Part


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-created ebook project inside a workspace."""

    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_workspace_id", "workspace_id"),
        Index("ix_projects_owner_user_id", "owner_user_id"),
        Index("ix_projects_status", "status"),
        Index("ix_projects_updated_at", "updated_at"),
    )

    workspace_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("workspaces.id"), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    folder_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("folders.id"))
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="projects")
    settings: Mapped[ProjectSettings] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    books: Mapped[list[Book]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Project-specific writing, formatting, image, AI, export, and KDP defaults."""

    __tablename__ = "project_settings"
    __table_args__ = (Index("ix_project_settings_project_id", "project_id", unique=True),)

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    book_size: Mapped[str] = mapped_column(String(40), default="6x9", nullable=False)
    custom_book_size: Mapped[dict[str, object] | None] = mapped_column(JSON)
    margins: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    font: Mapped[str] = mapped_column(String(120), default="Inter", nullable=False)
    theme: Mapped[str] = mapped_column(String(120), default="clean", nullable=False)
    writing_language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    image_ratio: Mapped[str] = mapped_column(String(40), default="16:9", nullable=False)
    image_style: Mapped[str] = mapped_column(String(80), default="realistic", nullable=False)
    image_color_theme: Mapped[str | None] = mapped_column(String(120))
    illustration_style: Mapped[str] = mapped_column(
        String(80),
        default="Photorealistic",
        nullable=False,
    )
    image_quality: Mapped[str] = mapped_column(String(40), default="high", nullable=False)
    default_ai_provider: Mapped[str] = mapped_column(String(80), default="openai", nullable=False)
    preferred_ai_provider: Mapped[str] = mapped_column(String(80), default="openai", nullable=False)
    preferred_ai_model: Mapped[str] = mapped_column(
        String(160),
        default="openai/gpt-4o-mini",
        nullable=False,
    )
    ai_temperature: Mapped[float] = mapped_column(default=0.7, nullable=False)
    ai_max_tokens: Mapped[int | None] = mapped_column(Integer)
    writing_style: Mapped[str | None] = mapped_column(Text)
    export_preferences: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    kdp_options: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    project: Mapped[Project] = relationship(back_populates="settings")


class Book(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Book container within a project."""

    __tablename__ = "books"
    __table_args__ = (
        Index("ix_books_project_id", "project_id"),
        Index("ix_books_status", "status"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(300))
    author_name: Mapped[str | None] = mapped_column(String(220))
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    target_audience: Mapped[str | None] = mapped_column(String(220))
    writing_style: Mapped[str | None] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    project: Mapped[Project] = relationship(back_populates="books")
    versions: Mapped[list[BookVersion]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )
    # Structured document hierarchy (see models/document.py). These are declared
    # as string-targeted relationships so the document module can be imported
    # without a hard import cycle at class-definition time.
    parts: Mapped[list[Part]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
        order_by="Part.position",
    )
    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
        order_by="Chapter.position",
    )
    # Phase 3 per-book assets and settings (see models/assets.py).
    book_settings: Mapped[BookSettings | None] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
        uselist=False,
    )
    image_assets: Mapped[list[ImageAsset]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )
    document_assets: Mapped[list[DocumentAsset]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )
    translation_records: Mapped[list[TranslationRecord]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )
    marketing_assets: Mapped[list[MarketingAsset]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )
    kdp_validation_reports: Mapped[list[KDPValidationReport]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )


class BookVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Version snapshot metadata for future book content revisions."""

    __tablename__ = "book_versions"
    __table_args__ = (
        UniqueConstraint("book_id", "version_number", name="uq_book_versions_book_version"),
        Index("ix_book_versions_book_id", "book_id"),
    )

    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(160))
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    book: Mapped[Book] = relationship(back_populates="versions")


class Folder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Project organization folder inside a workspace."""

    __tablename__ = "folders"
    __table_args__ = (
        Index("ix_folders_workspace_id", "workspace_id"),
        Index("ix_folders_parent_folder_id", "parent_folder_id"),
    )

    workspace_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("workspaces.id"), nullable=False)
    parent_folder_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("folders.id"))
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


from models.workspace import Workspace  # noqa: E402
