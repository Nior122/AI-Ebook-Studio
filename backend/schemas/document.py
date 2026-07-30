"""Pydantic schemas for the structured document hierarchy.

These mirror :class:`DocumentNode` for API boundaries and introduce level-
specific request/response models for CRUD operations on Parts, Chapters,
Sections, Paragraphs, and Sentences.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# DocumentNode — the canonical tree representation at the API boundary
# ---------------------------------------------------------------------------


class DocumentNodeSchema(BaseModel):
    """Serialized :class:`DocumentNode` for API responses.

    Future modules (Editing, Images, Translation, DOCX, KDP Validator) all
    accept this shape. It is a plain dict-tree, not an ORM model, so that
    frontend, services, and workers share a single contract.
    """

    id: UUID
    node_type: str = Field(..., pattern=r"^(project|book|part|chapter|section|paragraph|sentence)$")
    title: str | None = None
    text: str | None = None
    position: int = 0
    status: str = "draft"
    kind: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    attachments: dict[str, object] = Field(default_factory=dict)
    parent_id: UUID | None = None
    children: list[DocumentNodeSchema] = Field(default_factory=list)


class StructuredDocumentSchema(BaseModel):
    """API representation of a full book tree."""

    project_id: UUID
    book_id: UUID
    root: DocumentNodeSchema


# ---------------------------------------------------------------------------
# Per-level CRUD requests
# ---------------------------------------------------------------------------


class PartCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    slug: str = Field(min_length=1, max_length=320)
    position: int | None = None
    summary: str | None = None
    status: str = "draft"


class PartUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    slug: str | None = Field(default=None, min_length=1, max_length=320)
    position: int | None = None
    summary: str | None = None
    status: str | None = None


class PartResponse(BaseModel):
    id: UUID
    project_id: UUID
    book_id: UUID
    title: str
    slug: str
    position: int
    summary: str | None
    status: str
    word_count: int
    created_at: datetime
    updated_at: datetime
    chapter_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ChapterCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    slug: str = Field(min_length=1, max_length=320)
    part_id: UUID | None = None
    position: int | None = None
    summary: str | None = None
    status: str = "draft"


class ChapterUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    slug: str | None = Field(default=None, min_length=1, max_length=320)
    part_id: UUID | None = None
    position: int | None = None
    summary: str | None = None
    status: str | None = None


class ChapterResponse(BaseModel):
    id: UUID
    project_id: UUID
    book_id: UUID
    part_id: UUID | None
    title: str
    slug: str
    position: int
    summary: str | None
    status: str
    word_count: int
    created_at: datetime
    updated_at: datetime
    section_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SectionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    position: int | None = None
    status: str = "draft"


class SectionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    position: int | None = None
    status: str | None = None


class SectionResponse(BaseModel):
    id: UUID
    project_id: UUID
    book_id: UUID
    chapter_id: UUID
    title: str | None
    position: int
    status: str
    word_count: int
    created_at: datetime
    updated_at: datetime
    paragraph_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ParagraphCreateRequest(BaseModel):
    kind: str = "body"
    position: int | None = None
    status: str = "draft"


class ParagraphUpdateRequest(BaseModel):
    kind: str | None = None
    position: int | None = None
    status: str | None = None


class ParagraphResponse(BaseModel):
    id: UUID
    project_id: UUID
    book_id: UUID
    chapter_id: UUID
    section_id: UUID
    kind: str
    position: int
    status: str
    word_count: int
    created_at: datetime
    updated_at: datetime
    sentence_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SentenceCreateRequest(BaseModel):
    text: str = Field(min_length=1)
    kind: str = "body"
    position: int | None = None
    status: str = "draft"


class SentenceUpdateRequest(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    kind: str | None = None
    position: int | None = None
    status: str | None = None


class SentenceResponse(BaseModel):
    id: UUID
    project_id: UUID
    book_id: UUID
    chapter_id: UUID
    section_id: UUID
    paragraph_id: UUID
    text: str
    kind: str
    position: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
