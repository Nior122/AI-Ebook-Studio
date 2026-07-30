"""Book setup schemas.

These are the single-source-of-truth shapes for the Book Setup Page — the
one-screen workflow where the user supplies all the AI needs before
generation begins.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Generation parameters (creativity / speed)
# ---------------------------------------------------------------------------
CreativityLevel = Literal["creative", "balanced", "precise", "fast"]
SpeedLevel = Literal["fast", "balanced", "thorough"]


class AIGenerationSettings(BaseModel):
    """AI-side settings the user picks in the setup page."""

    creativity: CreativityLevel = "balanced"
    speed: SpeedLevel = "balanced"
    provider: str = Field(default="openrouter", description="AI provider id")
    model: str = Field(default="openai/gpt-4o-mini", description="Model id")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


# ---------------------------------------------------------------------------
# Layout settings
# ---------------------------------------------------------------------------
PageSize = Literal["6x9", "8x10", "A4", "custom"]
ImageRatio = Literal["16:9", "square", "portrait", "4:3"]
ImageStyle = Literal["realistic", "illustration", "watercolor", "sketch", "comic"]


class LayoutSettings(BaseModel):
    """Book layout / typography settings."""

    page_size: PageSize = "6x9"
    custom_page_size: dict[str, float] | None = None
    margins: dict[str, float] = Field(
        default_factory=lambda: {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        description="Page margins in inches",
    )
    header_font: str = "Georgia"
    header_size: int = 14
    body_font: str = "Georgia"
    body_size: int = 12
    line_spacing: float = 1.5
    paragraph_spacing: float = 1.0
    image_width: float = 6.0
    image_ratio: ImageRatio = "16:9"
    default_image_style: ImageStyle = "realistic"


# ---------------------------------------------------------------------------
# Book details
# ---------------------------------------------------------------------------
WritingTone = Literal[
    "conversational",
    "authoritative",
    "friendly",
    "professional",
    "academic",
    "humorous",
    "inspirational",
    "neutral",
]
WritingStyle = Literal[
    "storytelling",
    "instructional",
    "analytical",
    "descriptive",
    "persuasive",
    "practical_guide",
]


class BookDetails(BaseModel):
    """Core book identity — title, topic, audience, voice."""

    title: str = Field(min_length=1, max_length=300)
    subtitle: str | None = Field(default=None, max_length=300)
    topic: str = Field(min_length=1, description="What the book is about")
    target_audience: str = Field(min_length=1, description="Who the book is for")
    tone: WritingTone = "conversational"
    writing_style: WritingStyle = "practical_guide"
    language: str = Field(default="en", max_length=20)


# ---------------------------------------------------------------------------
# Book size
# ---------------------------------------------------------------------------
WORD_COUNT_PRESETS = (5000, 10000, 15000, 25000, 50000)


class BookSize(BaseModel):
    """Target length and derived chapter plan."""

    total_word_count: int = Field(ge=1000, le=200000)
    custom: bool = False

    @property
    def estimated_chapter_count(self) -> int:
        """Rough chapter count for the requested length."""
        if self.total_word_count <= 5000:
            return 5
        if self.total_word_count <= 10000:
            return 8
        if self.total_word_count <= 15000:
            return 10
        if self.total_word_count <= 25000:
            return 14
        if self.total_word_count <= 50000:
            return 20
        return 25


# ---------------------------------------------------------------------------
# Special instructions (free-form)
# ---------------------------------------------------------------------------
class SpecialInstructions(BaseModel):
    """User's free-form directives for the AI."""

    instructions: str = Field(default="", description="Anything special the AI should know")


# ---------------------------------------------------------------------------
# Full setup payload — one POST body for the whole flow
# ---------------------------------------------------------------------------
class BookSetupRequest(BaseModel):
    """Single screen payload for the entire book setup."""

    details: BookDetails
    size: BookSize
    layout: LayoutSettings = Field(default_factory=LayoutSettings)
    ai: AIGenerationSettings = Field(default_factory=AIGenerationSettings)
    special_instructions: SpecialInstructions = Field(default_factory=SpecialInstructions)


class BookSetupClarificationRequest(BaseModel):
    """Submitted user answers to the AI clarification questions."""

    setup: BookSetupRequest
    answers: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Setup response
# ---------------------------------------------------------------------------
class BookSetupResponse(BaseModel):
    """Response from POST /setup.

    Either contains a ``job_id`` (we're generating in the background), or
    ``clarification_questions`` (AI needs more information before starting).
    """

    project_id: UUID | None = None
    book_id: UUID | None = None
    writing_book_id: UUID | None = None
    job_id: UUID | None = None
    clarification_questions: list[dict[str, str]] | None = None


class GenerationClarifyResponse(BaseModel):
    """Response from POST /setup/clarify when AI needs answers."""

    questions: list[dict[str, str]]
    summary: str
