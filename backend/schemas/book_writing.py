"""Phase 6 — Pydantic request/response schemas for the book-writing engine.

Request schemas are optional-fielded for PATCH-style updates; response schemas
use ``ConfigDict(from_attributes=True)`` to build directly from ORM rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Book
# ---------------------------------------------------------------------------
class BookCreateRequest(BaseModel):
    """Create a new book (the 'Book Idea' step)."""

    title: str = Field(min_length=1, max_length=300)
    subtitle: str | None = Field(default=None, max_length=300)
    description: str | None = None
    author_name: str | None = Field(default=None, max_length=220)
    target_audience: str | None = Field(default=None, max_length=300)
    book_type: str | None = Field(default=None, max_length=80)
    language: str = Field(default="en", max_length=20)
    tone: str | None = Field(default=None, max_length=160)
    approximate_length: str | None = Field(default=None, max_length=80)


class BookUpdateRequest(BaseModel):
    """Editable book metadata (all optional for PATCH semantics)."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    subtitle: str | None = Field(default=None, max_length=300)
    description: str | None = None
    author_name: str | None = Field(default=None, max_length=220)
    target_audience: str | None = Field(default=None, max_length=300)
    book_type: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=20)
    tone: str | None = Field(default=None, max_length=160)
    approximate_length: str | None = Field(default=None, max_length=80)
    status: str | None = Field(default=None, max_length=40)
    current_step: str | None = Field(default=None, max_length=40)


class BookResponse(BaseModel):
    """Book aggregate read model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    subtitle: str | None = None
    description: str | None = None
    author_name: str | None = None
    target_audience: str | None = None
    book_type: str | None = None
    language: str
    tone: str | None = None
    approximate_length: str | None = None
    status: str
    current_step: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Book Brief
# ---------------------------------------------------------------------------
class BookBriefUpdateRequest(BaseModel):
    """Editable brief fields (all optional)."""

    working_title: str | None = None
    subtitle: str | None = None
    book_purpose: str | None = None
    target_reader: str | None = None
    reader_problems: list[str] | None = None
    promised_transformation: str | None = None
    tone: str | None = None
    writing_style: str | None = None
    key_themes: list[str] | None = None
    major_concepts: list[str] | None = None
    topics_to_avoid: list[str] | None = None
    suggested_structure: str | None = None
    estimated_chapter_count: int | None = None
    estimated_word_count: int | None = None
    raw_content: str | None = None


class BookBriefResponse(BaseModel):
    """Book brief read model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    working_title: str | None = None
    subtitle: str | None = None
    book_purpose: str | None = None
    target_reader: str | None = None
    reader_problems: list[str] = []
    promised_transformation: str | None = None
    tone: str | None = None
    writing_style: str | None = None
    key_themes: list[str] = []
    major_concepts: list[str] = []
    topics_to_avoid: list[str] = []
    suggested_structure: str | None = None
    estimated_chapter_count: int | None = None
    estimated_word_count: int | None = None
    raw_content: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Book Blueprint
# ---------------------------------------------------------------------------
class BlueprintChapterPlan(BaseModel):
    """A single chapter plan entry within a blueprint."""

    title: str
    objective: str | None = None
    summary: str | None = None
    key_lessons: list[str] = Field(default_factory=list)
    important_examples: list[str] = Field(default_factory=list)
    practical_exercises: list[str] = Field(default_factory=list)
    estimated_word_count: int | None = None
    connects_to_previous: str | None = None
    connects_to_future: str | None = None


class BookBlueprintUpdateRequest(BaseModel):
    """Editable blueprint fields (all optional)."""

    introduction_purpose: str | None = None
    chapters: list[BlueprintChapterPlan] | None = None
    estimated_total_word_count: int | None = None


class BookBlueprintResponse(BaseModel):
    """Book blueprint read model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    introduction_purpose: str | None = None
    chapters: list[BlueprintChapterPlan] = []
    estimated_total_word_count: int | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Chapter
# ---------------------------------------------------------------------------
class ChapterOutlineSection(BaseModel):
    """A section within a generated chapter outline."""

    title: str
    purpose: str | None = None
    key_points: list[str] = Field(default_factory=list)


class ChapterCreateRequest(BaseModel):
    """Create a chapter (optionally at a given position)."""

    title: str = Field(min_length=1, max_length=300)
    chapter_number: int | None = Field(default=None, ge=1)
    purpose: str | None = None
    objective: str | None = None
    summary: str | None = None
    target_word_count: int | None = Field(default=None, ge=0)


class ChapterUpdateRequest(BaseModel):
    """Editable chapter fields (all optional)."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    chapter_number: int | None = Field(default=None, ge=1)
    purpose: str | None = None
    objective: str | None = None
    summary: str | None = None
    outline: str | None = None
    outline_sections: list[ChapterOutlineSection] | None = None
    content: str | None = None
    status: str | None = Field(default=None, max_length=40)
    target_word_count: int | None = Field(default=None, ge=0)
    is_approved: bool | None = None


class ChapterRead(BaseModel):
    """Chapter read model (includes derived word count)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    chapter_number: int
    title: str
    purpose: str | None = None
    objective: str | None = None
    summary: str | None = None
    outline: str | None = None
    outline_sections: list[ChapterOutlineSection] = []
    content: str = ""
    status: str
    target_word_count: int | None = None
    actual_word_count: int
    is_approved: bool
    created_at: datetime
    updated_at: datetime


class ChapterReorderRequest(BaseModel):
    """Full 1..N reordering of a book's chapters by id."""

    chapter_ids: list[UUID]


# ---------------------------------------------------------------------------
# Chapter versions
# ---------------------------------------------------------------------------
class ChapterVersionResponse(BaseModel):
    """Chapter version read model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_id: UUID
    version_number: int
    content: str
    word_count: int
    version_type: str
    generation_metadata: dict[str, Any] = {}
    created_at: datetime
    created_by: UUID | None = None


# ---------------------------------------------------------------------------
# Manuscript
# ---------------------------------------------------------------------------
class ManuscriptResponse(BaseModel):
    """Manuscript snapshot read model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    full_text: str
    word_count: int
    chapter_order: list[UUID] = []
    is_stale: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Writing session (autosave)
# ---------------------------------------------------------------------------
class WritingSessionCreateRequest(BaseModel):
    """Begin / heartbeat a writing session."""

    chapter_id: UUID | None = None
    session_type: str = "autosave"
    resume_context: dict[str, Any] | None = None


class WritingSessionResponse(BaseModel):
    """Writing session read model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    user_id: UUID
    chapter_id: UUID | None = None
    session_type: str
    is_active: bool
    last_saved_at: datetime | None = None
    resume_context: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class AutosaveRequest(BaseModel):
    """Editor autosave payload (debounced from the UI)."""

    chapter_id: UUID
    content: str
    # Optional explicit version type for the snapshot.
    version_type: str = "user_edited"


# ---------------------------------------------------------------------------
# Book settings (writing style profile)
# ---------------------------------------------------------------------------
class BookSettingsUpdateRequest(BaseModel):
    """Editable per-book writing-style profile + generation preferences."""

    tone: str | None = None
    formality: str | None = None
    sentence_complexity: str | None = None
    paragraph_length: str | None = None
    use_examples: str | None = None
    use_stories: str | None = None
    use_analogies: str | None = None
    use_humor: str | None = None
    use_practical_exercises: str | None = None
    point_of_view: str | None = None
    reading_level: str | None = None
    preferred_provider: str | None = None
    preferred_model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    stream_responses: bool | None = None
    style_notes: str | None = None


class BookSettingsResponse(BaseModel):
    """Book settings read model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    tone: str | None = None
    formality: str | None = None
    sentence_complexity: str | None = None
    paragraph_length: str | None = None
    use_examples: str | None = None
    use_stories: str | None = None
    use_analogies: str | None = None
    use_humor: str | None = None
    use_practical_exercises: str | None = None
    point_of_view: str | None = None
    reading_level: str | None = None
    preferred_provider: str | None = None
    preferred_model: str | None = None
    temperature: float
    stream_responses: bool
    style_notes: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# AI action requests
# ---------------------------------------------------------------------------
class GenerateRequest(BaseModel):
    """Generic AI generation request scoped to a book/chapter."""

    provider: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    # Free-form instruction for rewrite/expand/shorten/tone actions.
    instruction: str | None = None
    # Selected text for inline actions (rewrite, expand, etc.).
    selected_text: str | None = None


# ---------------------------------------------------------------------------
# Workflow / status
# ---------------------------------------------------------------------------
class BookWorkflowResponse(BaseModel):
    """High-level workflow progress for a book."""

    book_id: UUID
    current_step: str
    status: str
    has_brief: bool
    has_blueprint: bool
    chapter_count: int
    approved_chapter_count: int
    version_count: int
