"""Database-driven RBAC helpers."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.accounts import Permission, Role, RolePermission, User
from models.workspace import Workspace, WorkspaceMember

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "owner": ["*"],
    "admin": [
        "workspace:read",
        "workspace:update",
        "workspace:invite",
        "project:create",
        "project:read",
        "project:update",
        "project:delete",
    ],
    "editor": ["workspace:read", "project:create", "project:read", "project:update"],
    "viewer": ["workspace:read", "project:read"],
    "future_ai_agent": ["project:read"],
}


async def ensure_rbac_seeded(session: AsyncSession) -> None:
    """Ensure default roles and permissions exist."""
    permission_keys = sorted({key for keys in ROLE_PERMISSIONS.values() for key in keys})
    permissions: dict[str, Permission] = {}
    for key in permission_keys:
        permission_result = await session.execute(select(Permission).where(Permission.key == key))
        permission = permission_result.scalar_one_or_none()
        if permission is None:
            permission = Permission(key=key, description=f"Allows {key}")
            session.add(permission)
            await session.flush()
        permissions[key] = permission

    for role_name, keys in ROLE_PERMISSIONS.items():
        role_result = await session.execute(select(Role).where(Role.name == role_name))
        role = role_result.scalar_one_or_none()
        if role is None:
            role = Role(name=role_name, description=f"{role_name.title()} role", is_system=True)
            session.add(role)
            await session.flush()

        for key in keys:
            permission = permissions[key]
            existing = await session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permission.id,
                ),
            )
            if existing.scalar_one_or_none() is None:
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))


async def get_role_by_name(session: AsyncSession, name: str) -> Role:
    """Return a role by normalized name."""
    normalized = name.lower()
    await ensure_rbac_seeded(session)
    result = await session.execute(select(Role).where(Role.name == normalized))
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid role.",
        )
    return role


async def get_workspace_member(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
) -> WorkspaceMember | None:
    """Return a user's active workspace membership."""
    result = await session.execute(
        select(WorkspaceMember)
        .join(Role)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.deleted_at.is_(None),
            WorkspaceMember.status == "active",
        ),
    )
    return result.scalar_one_or_none()


async def require_workspace_permission(
    session: AsyncSession,
    user: User,
    workspace_id: UUID,
    permission: str,
) -> WorkspaceMember:
    """Require a workspace permission for the current user."""
    result = await session.execute(
        select(WorkspaceMember, Role)
        .join(Role, WorkspaceMember.role_id == Role.id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.deleted_at.is_(None),
            WorkspaceMember.status == "active",
        ),
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace access denied.",
        )

    member, role = row
    allowed = ROLE_PERMISSIONS.get(role.name, [])
    if "*" not in allowed and permission not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    return cast(WorkspaceMember, member)


async def get_owned_workspace_or_404(
    session: AsyncSession,
    user: User,
    workspace_id: UUID,
) -> Workspace:
    """Return a workspace if the user is an active member."""
    await require_workspace_permission(session, user, workspace_id, "workspace:read")
    result = await session.execute(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.deleted_at.is_(None)),
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return workspace
