"""Chapter API schemas (create / read / update / reorder).

These drive the flat chapter API. ``content`` is a plain prose body; the service
computes ``word_count`` from it. ``chapter_number`` maps to the model's
``position`` (1-indexed for users).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChapterCreate(BaseModel):
    """Create a chapter within a book."""

    title: str = Field(min_length=1, max_length=300)
    content: str = Field(default="")
    chapter_number: int | None = Field(
        default=None,
        ge=1,
        description="Desired 1-indexed position; appended to the end if omitted.",
    )


class ChapterUpdate(BaseModel):
    """Update a chapter (all fields optional)."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = None
    chapter_number: int | None = Field(default=None, ge=1)
    status: str | None = None


class ChapterRead(BaseModel):
    """Chapter response."""

    id: UUID
    book_id: UUID
    chapter_number: int
    title: str
    content: str
    word_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChapterReorderItem(BaseModel):
    """A single (chapter_id, chapter_number) reorder instruction."""

    chapter_id: UUID
    chapter_number: int = Field(ge=1)


class ChapterReorderRequest(BaseModel):
    """Reorder multiple chapters in a book."""

    items: list[ChapterReorderItem] = Field(min_length=1)
