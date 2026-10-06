"""Request/response schemas for source-preserving translation editions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TranslationLanguage(BaseModel):
    code: str
    name: str


class TranslationRequest(BaseModel):
    source_language: str
    target_language: str
    translation_id: UUID | None = None


class TranslationChapterResponse(BaseModel):
    """A translated chapter snapshot, separate from its source chapter."""

    id: UUID
    translation_id: UUID
    source_chapter_id: UUID
    chapter_number: int
    title: str
    content: str
    word_count: int
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TranslationRecordResponse(BaseModel):
    """Summary of one independently stored translated edition."""

    id: UUID
    book_id: UUID
    source_language: str
    target_language: str
    status: str
    source_chapter_count: int
    translated_chapter_count: int
    target_word_count: int
    error_message: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TranslationEditionResponse(TranslationRecordResponse):
    """Translated-edition summary plus the persisted target-language chapters."""

    chapters: list[TranslationChapterResponse]


class TranslationListResponse(BaseModel):
    items: list[TranslationRecordResponse]
