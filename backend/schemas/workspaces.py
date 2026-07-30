"""Workspace schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreateRequest(BaseModel):
    """Create workspace request."""

    name: str = Field(min_length=1, max_length=220)
    description: str | None = None


class WorkspaceUpdateRequest(BaseModel):
    """Update workspace request."""

    name: str | None = Field(default=None, min_length=1, max_length=220)
    description: str | None = None
    status: str | None = None


class WorkspaceInviteRequest(BaseModel):
    """Workspace invite structure-only request."""

    email: str
    role: str = "viewer"


class WorkspaceResponse(BaseModel):
    """Workspace response."""

    id: UUID
    name: str
    slug: str
    status: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberResponse(BaseModel):
    """Workspace member response."""

    id: UUID
    user_id: UUID
    role: str
    status: str


class WorkspaceInviteResponse(BaseModel):
    """Workspace invite response."""

    accepted: bool
    message: str
