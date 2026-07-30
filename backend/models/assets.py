"""Phase 3 per-book asset and settings models.

These tables hang off a :class:`~models.project.Book` and are protected by the
same ownership chain (User → Workspace → Project → Book). They cover formatting
settings, generated images, generated documents, translations, marketing copy,
and KDP validation reports. Statuses/types are stored as strings for forward
compatibility; the canonical value sets live in :mod:`models.enums`.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.project import Book


class BookSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-controlled formatting settings for a book, applied before export.

    Defaults target a 6 x 9 inch trim with 16:9 images. The document-generation
    engine will read these values from the database rather than hardcoding them.
    """

    __tablename__ = "book_settings"
    __table_args__ = (Index("ix_book_settings_book_id", "book_id", unique=True),)

    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)

    # Page geometry (inches unless a named trim size overrides them).
    kdp_trim_size: Mapped[str] = mapped_column(String(40), default="6x9", nullable=False)
    custom_format_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    page_width: Mapped[float] = mapped_column(Float, default=6.0, nullable=False)
    page_height: Mapped[float] = mapped_column(Float, default=9.0, nullable=False)
    margin_top: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)
    margin_bottom: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)
    margin_left: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)
    margin_right: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)

    # Typography.
    body_font: Mapped[str] = mapped_column(String(120), default="Georgia", nullable=False)
    body_font_size: Mapped[float] = mapped_column(Float, default=11.0, nullable=False)
    heading_font: Mapped[str] = mapped_column(String(120), default="Georgia", nullable=False)
    line_spacing: Mapped[float] = mapped_column(Float, default=1.15, nullable=False)
    paragraph_spacing: Mapped[float] = mapped_column(Float, default=6.0, nullable=False)

    # Image defaults.
    image_width: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    image_alignment: Mapped[str] = mapped_column(String(40), default="center", nullable=False)
    image_aspect_ratio: Mapped[str] = mapped_column(String(40), default="16:9", nullable=False)
    image_style: Mapped[str] = mapped_column(String(80), default="realistic", nullable=False)
    caption_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    caption_font_size: Mapped[float] = mapped_column(Float, default=9.0, nullable=False)

    # Structure.
    chapter_page_breaks: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    toc_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    book: Mapped[Book] = relationship(back_populates="book_settings")


class ImageAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A generated image tied to a book (and optionally a chapter)."""

    __tablename__ = "image_assets"
    __table_args__ = (
        Index("ix_image_assets_project_id", "project_id"),
        Index("ix_image_assets_book_id", "book_id"),
        Index("ix_image_assets_chapter_id", "chapter_id"),
        Index("ix_image_assets_status", "status"),
    )

    project_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=True)
    book_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("books.id"), nullable=True)
    chapter_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("document_chapters.id")
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(80), default="pollinations", nullable=False)
    model: Mapped[str | None] = mapped_column(String(160))
    width: Mapped[int] = mapped_column(Integer, default=1600, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(40), default="16:9", nullable=False)
    file_url: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    position: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    book: Mapped[Book | None] = relationship(back_populates="image_assets")


class DocumentAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A generated document file (manuscript/DOCX/PDF/EPUB/cover/etc.)."""

    __tablename__ = "document_assets"
    __table_args__ = (
        Index("ix_document_assets_project_id", "project_id"),
        Index("ix_document_assets_book_id", "book_id"),
        Index("ix_document_assets_asset_type", "asset_type"),
        UniqueConstraint(
            "book_id", "asset_type", "version", name="uq_document_assets_book_type_version"
        ),
    )

    project_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=True)
    book_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("books.id"), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(60), nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    file_url: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    book: Mapped[Book | None] = relationship(back_populates="document_assets")


class TranslationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A translation of a book into a target language."""

    __tablename__ = "translation_records"
    __table_args__ = (
        Index("ix_translation_records_book_id", "book_id"),
        Index("ix_translation_records_status", "status"),
    )

    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    source_language: Mapped[str] = mapped_column(String(20), nullable=False)
    target_language: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    document_asset_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("document_assets.id")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    book: Mapped[Book | None] = relationship(back_populates="translation_records")


class MarketingAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """AI-generated marketing copy for a book."""

    __tablename__ = "marketing_assets"
    __table_args__ = (
        Index("ix_marketing_assets_book_id", "book_id"),
        Index("ix_marketing_assets_asset_type", "asset_type"),
    )

    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(60), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)

    book: Mapped[Book | None] = relationship(back_populates="marketing_assets")


class KDPValidationReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A KDP-readiness validation report for a book."""

    __tablename__ = "kdp_validation_reports"
    __table_args__ = (
        Index("ix_kdp_validation_reports_book_id", "book_id"),
        Index("ix_kdp_validation_reports_status", "status"),
    )

    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    issues: Mapped[list[object]] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[list[object]] = mapped_column(JSON, default=list, nullable=False)
    passed_checks: Mapped[list[object]] = mapped_column(JSON, default=list, nullable=False)

    book: Mapped[Book | None] = relationship(back_populates="kdp_validation_reports")
