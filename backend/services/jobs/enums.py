"""Canonical job types and lifecycle statuses.

These enums are the single source of truth shared by the API layer, the ``Job``
database model, and any future worker backend.
"""

from __future__ import annotations

from enum import StrEnum


class JobType(StrEnum):
    """All asynchronous job categories the platform will support."""

    BOOK_GENERATION = "BOOK_GENERATION"
    PROOFREADING = "PROOFREADING"
    IMAGE_ANALYSIS = "IMAGE_ANALYSIS"
    IMAGE_GENERATION = "IMAGE_GENERATION"
    DOCX_BUILD = "DOCX_BUILD"
    PDF_EXPORT = "PDF_EXPORT"
    EPUB_EXPORT = "EPUB_EXPORT"
    TRANSLATION = "TRANSLATION"
    MARKETING_GENERATION = "MARKETING_GENERATION"
    KDP_VALIDATION = "KDP_VALIDATION"
    COVER_GENERATION = "COVER_GENERATION"


class JobStatus(StrEnum):
    """Lifecycle states for a job."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` if no further transitions are expected."""
        return self in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
