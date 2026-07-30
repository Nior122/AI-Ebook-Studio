"""API schemas for Stage 8 image intelligence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImageAnalyzeRequest(BaseModel):
    book_id: UUID
    mode: str = Field(
        default="automatic",
        examples=["automatic", "low", "medium", "high", "custom"],
    )
    custom_count: int | None = Field(default=None, ge=0)


class ImagePlanRequest(ImageAnalyzeRequest):
    replace_existing: bool = True


class ImageGenerateRequest(BaseModel):
    plan_id: UUID | None = None
    provider: str = "pollinations"
    model: str | None = None
    title: str | None = None
    style: str | None = None
    aspect_ratio: str | None = None
    quality: str | None = None
    prompt_override: str | None = None
    negative_prompt_override: str | None = None
    seed: int | None = None


class ImageRegenerateRequest(BaseModel):
    image_id: UUID
    provider: str | None = None
    model: str | None = None
    style: str | None = None
    aspect_ratio: str | None = None
    quality: str | None = None
    prompt_override: str | None = None
    negative_prompt_override: str | None = None
    seed: int | None = None


class ImageReplaceRequest(BaseModel):
    image_id: UUID
    image_url: str
    prompt: str | None = None
    negative_prompt: str | None = None
    model: str = "external/manual"


class ImageUpdateRequest(BaseModel):
    title: str | None = None
    alt_text: str | None = None
    status: str | None = None
    restore_version_number: int | None = Field(default=None, ge=1)


class ImageSuggestionResponse(BaseModel):
    chapter_id: UUID
    chapter_title: str
    section_id: UUID
    section_title: str
    paragraph_id: UUID
    paragraph_preview: str
    subject: str
    rationale: str
    importance_score: float
    visual_complexity_score: float
    educational_value_score: float
    narrative_value_score: float
    recommended_order: int


class ChapterAnalysisResponse(BaseModel):
    chapter_id: UUID
    chapter_title: str
    recommended_count: int
    suggestions: list[ImageSuggestionResponse]


class ImagePlanResponse(BaseModel):
    id: UUID
    project_id: UUID
    book_id: UUID
    chapter_id: UUID
    section_id: UUID
    paragraph_id: UUID
    mode: str
    status: str
    title: str
    subject: str
    rationale: str | None
    importance_score: float
    visual_complexity_score: float
    educational_value_score: float
    narrative_value_score: float
    recommended_order: int
    aspect_ratio: str
    style: str
    color_theme: str | None
    quality: str
    prompt: str | None
    negative_prompt: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImagePlacementResponse(BaseModel):
    id: UUID
    project_id: UUID
    book_id: UUID
    chapter_id: UUID
    section_id: UUID
    paragraph_id: UUID
    plan_id: UUID | None
    generated_image_id: UUID | None
    alignment: str
    caption: str | None
    display_width: int | None
    display_height: int | None
    aspect_ratio: str
    position: str
    placement_order: int
    placement_label: str
    confidence_score: float

    model_config = ConfigDict(from_attributes=True)


class ImageVersionResponse(BaseModel):
    id: UUID
    version_number: int
    source_type: str
    status: str
    prompt: str
    negative_prompt: str
    provider_name: str
    model_name: str
    seed: int | None
    width: int
    height: int
    aspect_ratio: str
    generation_time_ms: float
    image_url: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobSummaryResponse(BaseModel):
    id: UUID
    status: str
    job_type: str

    model_config = ConfigDict(from_attributes=True)


class GeneratedImageResponse(BaseModel):
    id: UUID
    project_id: UUID
    book_id: UUID
    plan_id: UUID | None
    status: str
    title: str
    alt_text: str | None
    aspect_ratio: str
    style: str
    quality: str
    model_name: str | None
    provider_name: str | None
    seed: int | None
    width: int | None
    height: int | None
    current_version_number: int
    current_image_url: str | None
    created_at: datetime
    updated_at: datetime
    placement: ImagePlacementResponse | None = None
    versions: list[ImageVersionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ImageAnalysisResponse(BaseModel):
    book_id: UUID
    chapters: list[ChapterAnalysisResponse]
    total_recommended_images: int


class ImageGenerateResponse(BaseModel):
    image: GeneratedImageResponse
    job: JobSummaryResponse
