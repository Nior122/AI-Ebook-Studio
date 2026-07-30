"""Book settings API schemas (read / update).

Formatting settings are read/updated before final document generation. Defaults
mirror the model: a 6 x 9 inch trim with 16:9 images. All fields are editable.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BookSettingsUpdate(BaseModel):
    """Partial update of book formatting settings (all fields optional)."""

    kdp_trim_size: str | None = Field(
        default=None, examples=["6x9", "8x10", "A4", "Letter", "custom"]
    )
    custom_format_enabled: bool | None = None
    page_width: float | None = Field(default=None, gt=0)
    page_height: float | None = Field(default=None, gt=0)
    margin_top: float | None = Field(default=None, ge=0)
    margin_bottom: float | None = Field(default=None, ge=0)
    margin_left: float | None = Field(default=None, ge=0)
    margin_right: float | None = Field(default=None, ge=0)

    body_font: str | None = None
    body_font_size: float | None = Field(default=None, gt=0)
    heading_font: str | None = None
    line_spacing: float | None = Field(default=None, gt=0)
    paragraph_spacing: float | None = Field(default=None, ge=0)

    image_width: float | None = Field(default=None, gt=0)
    image_alignment: str | None = Field(default=None, examples=["left", "center", "right"])
    image_aspect_ratio: str | None = Field(default=None, examples=["16:9", "4:3", "1:1"])
    image_style: str | None = None
    caption_enabled: bool | None = None
    caption_font_size: float | None = Field(default=None, gt=0)

    chapter_page_breaks: bool | None = None
    toc_enabled: bool | None = None


class BookSettingsRead(BaseModel):
    """Book settings response."""

    id: UUID
    book_id: UUID
    kdp_trim_size: str
    custom_format_enabled: bool
    page_width: float
    page_height: float
    margin_top: float
    margin_bottom: float
    margin_left: float
    margin_right: float
    body_font: str
    body_font_size: float
    heading_font: str
    line_spacing: float
    paragraph_spacing: float
    image_width: float
    image_alignment: str
    image_aspect_ratio: str
    image_style: str
    caption_enabled: bool
    caption_font_size: float
    chapter_page_breaks: bool
    toc_enabled: bool

    model_config = ConfigDict(from_attributes=True)
