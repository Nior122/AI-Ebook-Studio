"""Phase 6 — Book Writing & Manuscript Management models.

These models implement a self-contained, user-owned book writing workflow:

    User
      └── Books
            ├── BookBrief
            ├── BookBlueprint (chapters)
            ├── Chapters
            │     └── ChapterVersions
            ├── Manuscript  (latest assembled/approved content snapshot)
            ├── WritingSession (autosave / generation bookkeeping)
            └── BookSettings (per-book writing-style profile + preferences)

Every entity is owned by a ``user_id`` and soft-deleted via ``deleted_at``
(from :class:`TimestampMixin`), so all access can be scoped by owner before any
row lookup — the foundation for IDOR protection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.accounts import User


# ---------------------------------------------------------------------------
# Book
# ---------------------------------------------------------------------------
class WritingBook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A book being written by a user.

    The book is the root aggregate of the Phase 6 workflow. It carries the
    high-level metadata entered at the 'Book Idea' step and tracks the current
    workflow position via ``status`` / ``current_step``.
    """

    __tablename__ = "bw_books"
    __table_args__ = (
        Index("ix_bw_books_user_id", "user_id"),
        Index("ix_bw_books_status", "status"),
        Index("ix_bw_books_current_step", "current_step"),
    )

    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=False
    )

    # --- Book idea / metadata ---
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(String(220))
    target_audience: Mapped[str | None] = mapped_column(String(300))
    book_type: Mapped[str | None] = mapped_column(String(80))  # e.g. nonfiction, novel, guide
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    tone: Mapped[str | None] = mapped_column(String(160))
    approximate_length: Mapped[str | None] = mapped_column(String(80))  # e.g. "60k words", "short"

    # --- Workflow state ---
    # Possible statuses:
    #   draft | planning | outlining | writing | editing
    #   | ready_for_formatting | completed
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    # current_step roughly maps to: idea | brief | blueprint | outline | writing
    #   | editing | formatting | export
    current_step: Mapped[str] = mapped_column(String(40), default="idea", nullable=False)

    # --- Relationships ---
    brief: Mapped[BookBrief | None] = relationship(
        back_populates="book", cascade="all, delete-orphan", uselist=False
    )
    blueprint: Mapped[BookBlueprint | None] = relationship(
        back_populates="book", cascade="all, delete-orphan", uselist=False
    )
    chapters: Mapped[list[WritingChapter]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
        order_by="WritingChapter.chapter_number",
    )
    settings: Mapped[WritingBookSettings | None] = relationship(
        back_populates="book", cascade="all, delete-orphan", uselist=False
    )
    manuscript: Mapped[Manuscript | None] = relationship(
        back_populates="book", cascade="all, delete-orphan", uselist=False
    )
    writing_sessions: Mapped[list[WritingSession]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])


# ---------------------------------------------------------------------------
# Book Brief
# ---------------------------------------------------------------------------
class BookBrief(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured analysis of a book idea, produced and editable by the user."""

    __tablename__ = "bw_book_briefs"
    __table_args__ = (
        UniqueConstraint("book_id", name="uq_bw_book_briefs_book_id"),
        Index("ix_bw_book_briefs_book_id", "book_id"),
    )

    book_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("bw_books.id"), nullable=False, unique=True
    )

    working_title: Mapped[str | None] = mapped_column(String(300))
    subtitle: Mapped[str | None] = mapped_column(String(300))
    book_purpose: Mapped[str | None] = mapped_column(Text)
    target_reader: Mapped[str | None] = mapped_column(Text)
    reader_problems: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    promised_transformation: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str | None] = mapped_column(String(160))
    writing_style: Mapped[str | None] = mapped_column(String(160))
    key_themes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    major_concepts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    topics_to_avoid: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    suggested_structure: Mapped[str | None] = mapped_column(Text)
    estimated_chapter_count: Mapped[int | None] = mapped_column(Integer)
    estimated_word_count: Mapped[int | None] = mapped_column(Integer)
    # Free-form notes the AI may have produced but the user can also edit.
    raw_content: Mapped[str | None] = mapped_column(Text)

    book: Mapped[WritingBook] = relationship(back_populates="brief")


# ---------------------------------------------------------------------------
# Book Blueprint
# ---------------------------------------------------------------------------
class BookBlueprint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Detailed, chapter-by-chapter plan for a book.

    The blueprint stores an ordered list of chapter-plan JSON blobs so the user
    can edit titles, reorder, add, delete, regenerate individual chapters, or
    regenerate the whole blueprint.
    """

    __tablename__ = "bw_book_blueprints"
    __table_args__ = (
        UniqueConstraint("book_id", name="uq_bw_book_blueprints_book_id"),
        Index("ix_bw_book_blueprints_book_id", "book_id"),
    )

    book_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("bw_books.id"), nullable=False, unique=True
    )

    introduction_purpose: Mapped[str | None] = mapped_column(Text)
    # Ordered chapter plans. Each entry is a dict shaped like:
    #   {
    #     "title": str,
    #     "objective": str,
    #     "summary": str,
    #     "key_lessons": list[str],
    #     "important_examples": list[str],
    #     "practical_exercises": list[str],
    #     "estimated_word_count": int,
    #     "connects_to_previous": str,
    #     "connects_to_future": str,
    #   }
    chapters: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    estimated_total_word_count: Mapped[int | None] = mapped_column(Integer)

    book: Mapped[WritingBook] = relationship(back_populates="blueprint")


# ---------------------------------------------------------------------------
# Chapter
# ---------------------------------------------------------------------------
class WritingChapter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single chapter of a book.

    Holds the latest approved/edited content in ``content`` plus planning fields.
    Historical snapshots live in :class:`ChapterVersion`.
    """

    __tablename__ = "bw_chapters"
    __table_args__ = (
        Index("ix_bw_chapters_book_id", "book_id"),
        Index("ix_bw_chapters_status", "status"),
        Index("ix_bw_chapters_book_number", "book_id", "chapter_number"),
    )

    book_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("bw_books.id"), nullable=False
    )

    # Possible statuses: planned | outlining | generating | draft
    #   | editing | approved | needs_revision
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    outline: Mapped[str | None] = mapped_column(Text)  # human-readable outline
    # Machine-readable outline used by the writing engine:
    #   [{"title": str, "purpose": str, "key_points": list[str]}]
    outline_sections: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="planned", nullable=False)
    target_word_count: Mapped[int | None] = mapped_column(Integer)
    actual_word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Whether the current content has unsaved/uncommitted AI edits.
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    book: Mapped[WritingBook] = relationship(back_populates="chapters")
    versions: Mapped[list[ChapterVersion]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="ChapterVersion.version_number",
    )


# ---------------------------------------------------------------------------
# Chapter Version
# ---------------------------------------------------------------------------
class ChapterVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An immutable snapshot of a chapter's content.

    Versions are never overwritten, enabling restore. ``version_type`` is one of
    ``ai_generated``, ``user_edited``, ``ai_edited``, ``approved``.
    """

    __tablename__ = "bw_chapter_versions"
    __table_args__ = (
        UniqueConstraint(
            "chapter_id", "version_number", name="uq_bw_chapter_versions_chapter_version"
        ),
        Index("ix_bw_chapter_versions_chapter_id", "chapter_id"),
    )

    chapter_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("bw_chapters.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version_type: Mapped[str] = mapped_column(
        String(40), default="ai_generated", nullable=False
    )
    # Generation metadata: provider, model, tokens_used, task, etc.
    generation_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_by: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))

    chapter: Mapped[WritingChapter] = relationship(back_populates="versions")


# ---------------------------------------------------------------------------
# Manuscript
# ---------------------------------------------------------------------------
class Manuscript(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Assembled manuscript snapshot for a book.

    Stores the assembled full-text content and a per-chapter ordering map so the
    editor / future export stages can reconstruct the book. Not the live source of
    truth (chapters are) — this is a convenience snapshot refreshed on demand.
    """

    __tablename__ = "bw_manuscripts"
    __table_args__ = (
        UniqueConstraint("book_id", name="uq_bw_manuscripts_book_id"),
        Index("ix_bw_manuscripts_book_id", "book_id"),
    )

    book_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("bw_books.id"), nullable=False, unique=True
    )
    full_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chapter_order: Mapped[list[UUID]] = mapped_column(JSON, default=list, nullable=False)
    # Whether the snapshot reflects the latest chapter content.
    is_stale: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    book: Mapped[WritingBook] = relationship(back_populates="manuscript")


# ---------------------------------------------------------------------------
# Writing Session
# ---------------------------------------------------------------------------
class WritingSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Bookkeeping for an autosave / generation session.

    Tracks the last autosave heartbeat and the currently active chapter so the UI
    can show reliable save state and the backend can detect stale locks.
    """

    __tablename__ = "bw_writing_sessions"
    __table_args__ = (
        Index("ix_bw_writing_sessions_book_id", "book_id"),
        Index("ix_bw_writing_sessions_user_id", "user_id"),
    )

    book_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("bw_books.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=False
    )
    chapter_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("bw_chapters.id"))
    # e.g. "autosave", "generation", "manual"
    session_type: Mapped[str] = mapped_column(String(40), default="autosave", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_saved_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Opaque cursor for resuming a continuation (offset into the chapter).
    resume_context: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    book: Mapped[WritingBook] = relationship(back_populates="writing_sessions")


# ---------------------------------------------------------------------------
# Book Settings (Writing Style Profile)
# ---------------------------------------------------------------------------
class WritingBookSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-book writing-style profile and content preferences.

    Configurable by the user and passed to the writing engine for every request.
    None of these are secrets; defaults come from the AI provider user preferences.
    """

    __tablename__ = "bw_book_settings"
    __table_args__ = (
        UniqueConstraint("book_id", name="uq_bw_book_settings_book_id"),
        Index("ix_bw_book_settings_book_id", "book_id"),
    )

    book_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("bw_books.id"), nullable=False, unique=True
    )

    # --- Writing style profile ---
    tone: Mapped[str | None] = mapped_column(String(160))
    formality: Mapped[str | None] = mapped_column(String(160))
    sentence_complexity: Mapped[str | None] = mapped_column(String(80))
    paragraph_length: Mapped[str | None] = mapped_column(String(80))
    use_examples: Mapped[str | None] = mapped_column(String(40), default="medium")
    use_stories: Mapped[str | None] = mapped_column(String(40), default="medium")
    use_analogies: Mapped[str | None] = mapped_column(String(40), default="low")
    use_humor: Mapped[str | None] = mapped_column(String(40), default="low")
    use_practical_exercises: Mapped[str | None] = mapped_column(String(40), default="medium")
    point_of_view: Mapped[str | None] = mapped_column(String(40), default="second_person")
    reading_level: Mapped[str | None] = mapped_column(String(80), default="general")

    # --- Generation preferences ---
    # Preferred provider/model for this book's AI work (provider-agnostic).
    preferred_provider: Mapped[str | None] = mapped_column(String(80))
    preferred_model: Mapped[str | None] = mapped_column(String(160))
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    # Whether to stream generation in the editor.
    stream_responses: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Free-form style guidance appended to prompts.
    style_notes: Mapped[str | None] = mapped_column(Text)

    book: Mapped[WritingBook] = relationship(back_populates="settings")
