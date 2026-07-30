"""Marketing schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MarketingAssetTypeInfo(BaseModel):
    """Metadata about a marketing asset type."""

    type_id: str
    label: str
    description: str


class MarketingAssetResponse(BaseModel):
    """Marketing asset response."""

    id: UUID
    book_id: UUID
    asset_type: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MarketingListResponse(BaseModel):
    """List of marketing assets."""

    items: list[MarketingAssetResponse]