"""Translation schemas."""

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


class TranslationRecordResponse(BaseModel):
    id: UUID
    book_id: UUID
    source_language: str
    target_language: str
    status: str
    document_asset_id: UUID | None
    completed_at: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TranslationListResponse(BaseModel):
    items: list[TranslationRecordResponse]