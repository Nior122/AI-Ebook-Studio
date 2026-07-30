"""Canonical string enum value sets for model/schema validation.

Models store these as plain strings for forward compatibility; schemas and
services use these enums to validate and constrain accepted values.
"""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    """Lifecycle status for a project."""

    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class BookStatus(StrEnum):
    """Lifecycle status for a book."""

    DRAFT = "DRAFT"
    WRITING = "WRITING"
    EDITING = "EDITING"
    READY_FOR_FORMATTING = "READY_FOR_FORMATTING"
    COMPLETED = "COMPLETED"


class AIJobType(StrEnum):
    """Persistent job categories (superset of the queue's JobType)."""

    BOOK_GENERATION = "BOOK_GENERATION"
    BOOK_EDITING = "BOOK_EDITING"
    IMAGE_ANALYSIS = "IMAGE_ANALYSIS"
    IMAGE_GENERATION = "IMAGE_GENERATION"
    DOCX_BUILD = "DOCX_BUILD"
    PDF_EXPORT = "PDF_EXPORT"
    EPUB_EXPORT = "EPUB_EXPORT"
    KDP_VALIDATION = "KDP_VALIDATION"
    COVER_GENERATION = "COVER_GENERATION"
    PROOFREADING = "PROOFREADING"
    TRANSLATION = "TRANSLATION"
    MARKETING_GENERATION = "MARKETING_GENERATION"


class AIJobStatus(StrEnum):
    """Persistent job lifecycle statuses."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ImageAssetStatus(StrEnum):
    """Lifecycle status for a generated image asset."""

    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REPLACED = "REPLACED"


class ImagePlanStatus(StrEnum):
    """Lifecycle status for an AI image plan."""

    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class DocumentAssetType(StrEnum):
    """Kinds of generated document files."""

    MANUSCRIPT = "MANUSCRIPT"
    MARKED_MANUSCRIPT = "MARKED_MANUSCRIPT"
    DOCX = "DOCX"
    PDF = "PDF"
    EPUB = "EPUB"
    COVER = "COVER"
    TRANSLATION = "TRANSLATION"
    MARKETING_PACK = "MARKETING_PACK"


class TranslationStatus(StrEnum):
    """Lifecycle status for a translation record."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MarketingAssetType(StrEnum):
    """Kinds of AI marketing outputs."""

    AMAZON_DESCRIPTION = "AMAZON_DESCRIPTION"
    SUBTITLE = "SUBTITLE"
    KEYWORDS = "KEYWORDS"
    CATEGORIES = "CATEGORIES"
    PINTEREST_POST = "PINTEREST_POST"
    INSTAGRAM_CAPTION = "INSTAGRAM_CAPTION"
    FACEBOOK_POST = "FACEBOOK_POST"
    X_POST = "X_POST"
    LINKEDIN_POST = "LINKEDIN_POST"
    EMAIL_PROMOTION = "EMAIL_PROMOTION"


class KDPValidationStatus(StrEnum):
    """Lifecycle status for a KDP validation report."""

    PENDING = "PENDING"
    PASSED = "PASSED"
    PASSED_WITH_WARNINGS = "PASSED_WITH_WARNINGS"
    FAILED = "FAILED"


# Named page trim sizes supported by book settings. Custom sizes use
# ``custom_format_enabled`` with explicit page_width/page_height.
TRIM_SIZES: dict[str, tuple[float, float]] = {
    "6x9": (6.0, 9.0),
    "8x10": (8.0, 10.0),
    "A4": (8.27, 11.69),
    "Letter": (8.5, 11.0),
}
