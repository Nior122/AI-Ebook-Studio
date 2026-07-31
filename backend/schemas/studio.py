"""Studio UX API schemas — autosave, versions, activities, notifications,
bookmarks, project search, stage management, the assistant, and per-user
AI provider keys.

These shapes are the single source of truth for the unified workspace UI.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Autosave
# ---------------------------------------------------------------------------
class AutosaveRequest(BaseModel):
    """Bulk chapter autosave (debounced client-side)."""

    chapters: dict[str, str] = Field(
        default_factory=dict, description="chapter_id -> latest markdown content"
    )


class AutosaveResponse(BaseModel):
    """Confirmation returned by the autosave endpoint."""

    saved_at: datetime
    saved_chapters: int
    revision: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Versions (restore points)
# ---------------------------------------------------------------------------
class VersionCreate(BaseModel):
    """Create a manual project restore point."""

    label: str = Field(min_length=1, max_length=300)
    reason: str | None = Field(default=None, max_length=2000)


class VersionRead(BaseModel):
    """Project version (restore point) summary."""

    id: UUID
    project_id: UUID
    label: str
    reason: str | None
    created_by: str
    created_at: datetime


class RestoreResponse(BaseModel):
    """Result of restoring a project version."""

    version_id: UUID
    restored: bool
    chapters_updated: int
    message: str


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------
class ActivityRead(BaseModel):
    """One entry in the project activity timeline."""

    id: UUID
    project_id: UUID
    kind: str
    message: str
    meta: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class NotificationRead(BaseModel):
    """A durable user notification."""

    id: UUID
    project_id: UUID | None
    kind: str
    title: str
    body: str | None
    level: str
    read_at: datetime | None
    action_type: str | None
    action_payload: dict[str, object] | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated notification list with an unread count."""

    items: list[NotificationRead]
    unread: int


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------
class BookmarkCreate(BaseModel):
    """Create a bookmark."""

    chapter_id: UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    note: str | None = Field(default=None, max_length=2000)


class BookmarkRead(BaseModel):
    """Bookmark response."""

    id: UUID
    project_id: UUID
    chapter_id: UUID | None
    title: str
    note: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Project search
# ---------------------------------------------------------------------------
class SearchResult(BaseModel):
    """A single manuscript search hit."""

    type: Literal["chapter", "heading", "image_caption"]
    chapter_id: UUID | None
    chapter_title: str
    snippet: str
    heading: str | None = None
    image_url: str | None = None


class SearchResponse(BaseModel):
    """Search results across the whole manuscript."""

    query: str
    results: list[SearchResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Project stage
# ---------------------------------------------------------------------------
ProjectStage = Literal["draft", "generating", "review", "ready_for_export", "published"]

STAGE_LABELS: dict[str, str] = {
    "draft": "Draft",
    "generating": "Generating",
    "review": "Review",
    "ready_for_export": "Ready for Export",
    "published": "Published",
}


class StageUpdate(BaseModel):
    """Set the project lifecycle stage."""

    stage: ProjectStage


class StageResponse(BaseModel):
    """Project stage confirmation."""

    project_id: UUID
    stage: str
    label: str


# ---------------------------------------------------------------------------
# AI assistant (workspace)
# ---------------------------------------------------------------------------
class AssistantRequest(BaseModel):
    """Ask the AI assistant to help with the current book/chapter."""

    message: str = Field(min_length=1, max_length=4000)
    chapter_id: UUID | None = None
    action: Literal["chat", "rewrite", "continue", "expand", "shorten", "fix_grammar"] | None = None


class AssistantResponse(BaseModel):
    """Assistant reply — a message and, for edit actions, the new content."""

    reply: str
    applied: bool = False
    new_content: str | None = None


# ---------------------------------------------------------------------------
# Per-user AI provider keys
# ---------------------------------------------------------------------------
class ProviderKeyRequest(BaseModel):
    """Store (encrypted) a user-supplied AI provider API key."""

    provider: str = Field(min_length=1, max_length=80)
    api_key: str = Field(min_length=8, max_length=500)


class ProviderKeyStatus(BaseModel):
    """Whether the user has a stored key for a provider (never the key itself)."""

    provider: str | None
    has_key: bool
