"""SQLAlchemy models for the Image Intelligence Engine."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class ImageProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configured image provider metadata and health state."""

    __tablename__ = "image_providers"
    __table_args__ = (
        Index("ix_image_providers_name", "name", unique=True),
        Index("ix_image_providers_enabled", "is_enabled"),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_base_url: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_health_status: Mapped[bool | None] = mapped_column(Boolean)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class ImagePlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One planned image suggestion anchored to a manuscript node."""

    __tablename__ = "image_plans"
    __table_args__ = (
        Index("ix_image_plans_project_id", "project_id"),
        Index("ix_image_plans_book_id", "book_id"),
        Index("ix_image_plans_chapter_id", "chapter_id"),
        Index("ix_image_plans_status", "status"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    chapter_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("document_chapters.id"),
        nullable=False,
    )
    section_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("document_sections.id"),
        nullable=False,
    )
    paragraph_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("document_paragraphs.id"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(String(40), default="automatic", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="planned", nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    visual_complexity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    educational_value_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    narrative_value_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recommended_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="16:9", nullable=False)
    style: Mapped[str] = mapped_column(String(80), default="Photorealistic", nullable=False)
    color_theme: Mapped[str | None] = mapped_column(String(120))
    quality: Mapped[str] = mapped_column(String(40), default="high", nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text)
    negative_prompt: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    placements: Mapped[list[ImagePlacement]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    images: Mapped[list[GeneratedImage]] = relationship(back_populates="plan")


class ImagePlacement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured image placement plan row used later by the Export Engine."""

    __tablename__ = "image_placements"
    __table_args__ = (
        Index("ix_image_placements_project_id", "project_id"),
        Index("ix_image_placements_book_id", "book_id"),
        Index("ix_image_placements_image_id", "generated_image_id"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    chapter_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("document_chapters.id"),
        nullable=False,
    )
    section_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("document_sections.id"),
        nullable=False,
    )
    paragraph_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("document_paragraphs.id"),
        nullable=False,
    )
    plan_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("image_plans.id"))
    generated_image_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("generated_images.id")
    )
    alignment: Mapped[str] = mapped_column(String(40), default="center", nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    display_width: Mapped[int | None] = mapped_column(Integer)
    display_height: Mapped[int | None] = mapped_column(Integer)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="16:9", nullable=False)
    position: Mapped[str] = mapped_column(String(80), default="after_paragraph", nullable=False)
    placement_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    placement_label: Mapped[str] = mapped_column(
        String(80), default="after_paragraph", nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    plan: Mapped[ImagePlan | None] = relationship(back_populates="placements")
    image: Mapped[GeneratedImage | None] = relationship(back_populates="placement")


class GeneratedImage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Logical image asset with a current active version."""

    __tablename__ = "generated_images"
    __table_args__ = (
        Index("ix_generated_images_project_id", "project_id"),
        Index("ix_generated_images_book_id", "book_id"),
        Index("ix_generated_images_status", "status"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    plan_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("image_plans.id"))
    provider_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("image_providers.id"))
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(Text)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="16:9", nullable=False)
    style: Mapped[str] = mapped_column(String(80), default="Photorealistic", nullable=False)
    quality: Mapped[str] = mapped_column(String(40), default="high", nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120))
    provider_name: Mapped[str | None] = mapped_column(String(80))
    seed: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    current_version_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_image_url: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    plan: Mapped[ImagePlan | None] = relationship(back_populates="images")
    placement: Mapped[ImagePlacement | None] = relationship(back_populates="image", uselist=False)
    versions: Mapped[list[ImageVersion]] = relationship(
        back_populates="image",
        cascade="all, delete-orphan",
        order_by="ImageVersion.version_number",
    )


class ImageVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable version history for every generated image."""

    __tablename__ = "image_versions"
    __table_args__ = (
        Index("ix_image_versions_image_id", "generated_image_id"),
        Index("ix_image_versions_version_number", "generated_image_id", "version_number"),
    )

    generated_image_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("generated_images.id"),
        nullable=False,
    )
    provider_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("image_providers.id"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="generated", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="completed", nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(20), nullable=False)
    generation_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    image: Mapped[GeneratedImage] = relationship(back_populates="versions")
