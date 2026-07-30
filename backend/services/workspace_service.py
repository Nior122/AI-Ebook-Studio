"""Workspace service."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.accounts import User
from models.workspace import Workspace, WorkspaceMember
from schemas.workspaces import WorkspaceCreateRequest, WorkspaceUpdateRequest
from services.rbac_service import get_role_by_name, require_workspace_permission


def slugify(value: str) -> str:
    """Create a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "workspace"


async def list_workspaces(session: AsyncSession, user: User) -> list[Workspace]:
    """List workspaces visible to a user."""
    result = await session.execute(
        select(Workspace)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.deleted_at.is_(None),
            Workspace.deleted_at.is_(None),
        )
        .order_by(Workspace.updated_at.desc()),
    )
    return list(result.scalars().unique())


async def create_workspace(
    session: AsyncSession,
    user: User,
    payload: WorkspaceCreateRequest,
) -> Workspace:
    """Create a workspace owned by a user."""
    role = await get_role_by_name(session, "owner")
    workspace = Workspace(
        owner_user_id=user.id,
        name=payload.name,
        slug=f"{slugify(payload.name)}-{user.id.hex[:8]}",
        description=payload.description,
        status="active",
    )
    session.add(workspace)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def update_workspace(
    session: AsyncSession,
    user: User,
    workspace_id: UUID,
    payload: WorkspaceUpdateRequest,
) -> Workspace:
    """Update a workspace."""
    await require_workspace_permission(session, user, workspace_id, "workspace:update")
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None or workspace.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    if payload.name is not None:
        workspace.name = payload.name
        workspace.slug = f"{slugify(payload.name)}-{workspace.id.hex[:8]}"
    if payload.description is not None:
        workspace.description = payload.description
    if payload.status is not None:
        workspace.status = payload.status
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def soft_delete_workspace(session: AsyncSession, user: User, workspace_id: UUID) -> None:
    """Soft delete a workspace."""
    await require_workspace_permission(session, user, workspace_id, "workspace:update")
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None or workspace.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    workspace.deleted_at = datetime.now(UTC)
    workspace.status = "deleted"
    await session.commit()


async def archive_workspace(session: AsyncSession, user: User, workspace_id: UUID) -> Workspace:
    """Archive a workspace."""
    return await update_workspace(
        session,
        user,
        workspace_id,
        WorkspaceUpdateRequest(status="archived"),
    )


async def get_or_create_default_workspace(session: AsyncSession, user: User) -> Workspace:
    """Return the user's first workspace, or create one automatically."""
    result = await session.execute(
        select(Workspace)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == user.id, WorkspaceMember.deleted_at.is_(None))
        .order_by(Workspace.created_at)
        .limit(1)
    )
    ws = result.scalar()
    if ws:
        return ws
    return await create_workspace(
        session, user,
        WorkspaceCreateRequest(name="My Workspace", description="Default workspace"),
    )
