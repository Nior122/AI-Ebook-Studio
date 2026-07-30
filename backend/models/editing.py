"""Phase 7 — AI Manuscript Editing & Proofreading models.

These models implement the AI editing pipeline on top of the Phase 6
Book → Chapter → ChapterVersion architecture:

    EditingSession        (a review/proofread/engineering pass on a chapter)
      └── EditingSuggestion (a single AI-proposed change, never auto-applied)

    ReviewJob              (a batch review across one book's chapters)

Every entity is owned transitively by a user via the chapter's book, so all
access can be scoped by owner before any row lookup — IDOR protection.
Suggestion rows are never deleted; they move through status states
(pending → accepted | rejected | ignored). Accepting a suggestion applies the
suggested text to the chapter content and creates a new ChapterVersion
(append-only), so the user can always restore the pre-edit version.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.book_writing import WritingChapter


# ---------------------------------------------------------------------------
# EditingSession
# ---------------------------------------------------------------------------
class EditingSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single editing pass (proofread, clarity, style, …) on one chapter.

    Groups the suggestions produced by one AI review request and tracks the
    mode used (proofreading, clarity_editing, style_editing, structural_editing,
    consistency_check, repetition_check, full_review). A chapter may have many
    sessions (one per review run); suggestions always belong to exactly one
    session.
    """

    __tablename__ = "ed_sessions"
    __table_args__ = (
        Index("ix_ed_sessions_chapter_id", "chapter_id"),
        Index("ix_ed_sessions_book_id", "book_id"),
        Index("ix_ed_sessions_status", "status"),
    )

    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("bw_books.id"), nullable=False)
    chapter_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("bw_chapters.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="running", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    suggestions: Mapped[list[EditingSuggestion]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    chapter: Mapped["WritingChapter"] = relationship()


# ---------------------------------------------------------------------------
# EditingSuggestion
# ---------------------------------------------------------------------------
class EditingSuggestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single AI-proposed manuscript change, reviewable by the user.

    The manuscript is never modified by suggestion creation — the user must
    explicitly accept a suggestion for its `suggested_text` to be spliced into
    the chapter content (creating a new ChapterVersion). Rejecting or ignoring
    leaves the chapter untouched.
    """

    __tablename__ = "ed_suggestions"
    __table_args__ = (
        Index("ix_ed_suggestions_chapter_id", "chapter_id"),
        Index("ix_ed_suggestions_session_id", "session_id"),
        Index("ix_ed_suggestions_status", "status"),
        Index("ix_ed_suggestions_category", "category"),
        Index("ix_ed_suggestions_severity", "severity"),
    )

    chapter_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("bw_chapters.id"), nullable=False)
    session_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("ed_sessions.id"), nullable=False)
    # Which batch (review-job) this suggestion belongs to — nullable when the
    # suggestion was created by a single-chapter / selection review.
    batch_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("ed_batches.id"), nullable=True)

    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="low", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stable location descriptor. JSON rather than (start,end) ints because
    # proposed edits can be paraphrases spanning non-contiguous text. Shape:
    #   {"start": int, "end": int, "anchor": "..." | null}
    location_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ignored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[EditingSession] = relationship(back_populates="suggestions")
    batch: Mapped[SuggestionBatch | None] = relationship(back_populates="suggestions")
    chapter: Mapped["WritingChapter"] = relationship()


# ---------------------------------------------------------------------------
# SuggestionBatch
# ---------------------------------------------------------------------------
class SuggestionBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A batch of suggestions produced by a single review pass.

    A batch groups all suggestions created by one AI call (chapter review or
    selected-text review). Accepting/rejecting "all suggestions" operates on a
    batch. Batches also track which batch superseded them when a user
    regenerates or accepts a conflicting suggestion so the UI can hide stale
    suggestions.
    """

    __tablename__ = "ed_batches"
    __table_args__ = (
        Index("ix_ed_batches_chapter_id", "chapter_id"),
        Index("ix_ed_batches_session_id", "session_id"),
    )

    chapter_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("bw_chapters.id"), nullable=False)
    session_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("ed_sessions.id"), nullable=False)
    label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    superseded_by_batch_id: Mapped[UUID | None] = mapped_column(GUID(), nullable=True)

    suggestions: Mapped[list[EditingSuggestion]] = relationship(back_populates="batch")


# ---------------------------------------------------------------------------
# ReviewJob
# ---------------------------------------------------------------------------
class ReviewJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A background batch review across a whole book (or subset of chapters).

    The job processes one chapter at a time, persisting suggestions as it goes,
    so the UI can show live progress (queued → processing → saving → done).
    A user can leave the page and poll the job status later.
    """

    __tablename__ = "ed_review_jobs"
    __table_args__ = (
        Index("ix_ed_review_jobs_book_id", "book_id"),
        Index("ix_ed_review_jobs_status", "status"),
    )

    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("bw_books.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    chapter_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("bw_chapters.id"), nullable=True)

    # Modes: full_manuscript | chapter_review | selected_text | proofread
    # | clarity | style | structure | consistency | repetition
    mode: Mapped[str] = mapped_column(String(60), nullable=False)
    # Status: queued | processing | saving_suggestions | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)

    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Per-chapter processing metadata: [{"chapter_id": str, "status": str, "suggestion_count": int}]
    progress_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=list, nullable=False)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
