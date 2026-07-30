"""Project, settings, and book schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectSettingsRequest(BaseModel):
    """Editable project settings."""

    book_size: str | None = Field(default=None, examples=["6x9", "8x10", "A4", "custom"])
    custom_book_size: dict[str, object] | None = None
    margins: dict[str, object] | None = None
    font: str | None = None
    theme: str | None = None
    writing_language: str | None = None
    image_ratio: str | None = Field(default=None, examples=["16:9", "square", "portrait"])
    image_style: str | None = Field(
        default=None,
        examples=["realistic", "illustration", "sketch", "comic", "watercolor"],
    )
    image_color_theme: str | None = None
    illustration_style: str | None = Field(
        default=None,
        examples=["Photorealistic", "Digital Painting", "Watercolor", "Anime"],
    )
    image_quality: str | None = Field(default=None, examples=["standard", "high", "ultra"])
    default_ai_provider: str | None = Field(
        default=None,
        examples=["openai", "anthropic", "gemini", "openrouter"],
    )
    preferred_ai_provider: str | None = Field(
        default=None,
        examples=["openai", "anthropic", "gemini", "openrouter", "groq", "ollama"],
    )
    preferred_ai_model: str | None = Field(default=None, examples=["openai/gpt-4o-mini"])
    ai_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    ai_max_tokens: int | None = Field(default=None, ge=1)
    writing_style: str | None = None
    export_preferences: dict[str, object] | None = None
    kdp_options: dict[str, object] | None = None


class ProjectSettingsResponse(BaseModel):
    """Project settings response."""

    id: UUID
    project_id: UUID
    book_size: str
    custom_book_size: dict[str, object] | None
    margins: dict[str, object]
    font: str
    theme: str
    writing_language: str
    image_ratio: str
    image_style: str
    image_color_theme: str | None
    illustration_style: str
    image_quality: str
    default_ai_provider: str
    preferred_ai_provider: str
    preferred_ai_model: str
    ai_temperature: float
    ai_max_tokens: int | None
    writing_style: str | None
    export_preferences: dict[str, object]
    kdp_options: dict[str, object]

    model_config = ConfigDict(from_attributes=True)


class ProjectCreateRequest(BaseModel):
    """Create project request."""

    workspace_id: UUID
    name: str = Field(min_length=1, max_length=220)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    settings: ProjectSettingsRequest | None = None


class ProjectUpdateRequest(BaseModel):
    """Update project request."""

    name: str | None = Field(default=None, min_length=1, max_length=220)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    status: str | None = None
    is_favorite: bool | None = None


class ProjectResponse(BaseModel):
    """Project response."""

    id: UUID
    workspace_id: UUID
    owner_user_id: UUID
    name: str
    title: str
    description: str | None
    status: str
    is_favorite: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookCreateRequest(BaseModel):
    """Create book request."""

    title: str = Field(min_length=1, max_length=300)
    subtitle: str | None = None
    author_name: str | None = None
    description: str | None = None
    language: str = Field(default="en", max_length=20)
    target_audience: str | None = Field(default=None, max_length=220)
    writing_style: str | None = Field(default=None, max_length=220)


class BookUpdateRequest(BaseModel):
    """Update book request (all fields optional)."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    subtitle: str | None = None
    author_name: str | None = None
    description: str | None = None
    language: str | None = Field(default=None, max_length=20)
    target_audience: str | None = Field(default=None, max_length=220)
    writing_style: str | None = Field(default=None, max_length=220)
    status: str | None = None


class BookResponse(BaseModel):
    """Book response."""

    id: UUID
    project_id: UUID
    title: str
    subtitle: str | None
    author_name: str | None
    description: str | None = None
    language: str = "en"
    target_audience: str | None = None
    writing_style: str | None = None
    status: str
    metadata_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
