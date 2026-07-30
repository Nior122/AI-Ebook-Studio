"""Export schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExportRequest(BaseModel):
    """Request to export a book to a downloadable format."""

    format: str = Field(description="docx | pdf | epub")
    include_front_matter: bool = True
    include_toc: bool = True
    include_back_matter: bool = False


class ExportResponse(BaseModel):
    """Response after a successful export."""

    id: UUID
    book_id: UUID
    asset_type: str
    file_name: str
    file_url: str
    file_size: int
    mime_type: str
    version: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExportListResponse(BaseModel):
    """List of exports for a book."""

    items: list[ExportResponse]


class ExportFormatInfo(BaseModel):
    """Metadata about an available export format."""

    format: str
    label: str
    mime_type: str
    extension: str
    description: str
