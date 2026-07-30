"""Workspace endpoints."""

from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import CurrentUser, DatabaseSession
from schemas.auth import MessageResponse
from schemas.workspaces import (
    WorkspaceCreateRequest,
    WorkspaceInviteRequest,
    WorkspaceInviteResponse,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from services.workspace_service import (
    archive_workspace,
    create_workspace,
    list_workspaces,
    soft_delete_workspace,
    update_workspace,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceResponse], summary="List workspaces")
async def get_workspaces(session: DatabaseSession, user: CurrentUser) -> list[WorkspaceResponse]:
    """List workspaces available to the authenticated user."""
    workspaces = await list_workspaces(session, user)
    return [WorkspaceResponse.model_validate(workspace) for workspace in workspaces]


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workspace",
)
async def post_workspace(
    payload: WorkspaceCreateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> WorkspaceResponse:
    """Create a workspace owned by the authenticated user."""
    workspace = await create_workspace(session, user, payload)
    return WorkspaceResponse.model_validate(workspace)


@router.put("/{workspace_id}", response_model=WorkspaceResponse, summary="Update workspace")
async def put_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> WorkspaceResponse:
    """Rename, update, or change workspace status."""
    workspace = await update_workspace(session, user, workspace_id, payload)
    return WorkspaceResponse.model_validate(workspace)


@router.post(
    "/{workspace_id}/archive",
    response_model=WorkspaceResponse,
    summary="Archive workspace",
)
async def post_archive_workspace(
    workspace_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> WorkspaceResponse:
    """Archive a workspace."""
    workspace = await archive_workspace(session, user, workspace_id)
    return WorkspaceResponse.model_validate(workspace)


@router.delete("/{workspace_id}", response_model=MessageResponse, summary="Delete workspace")
async def delete_workspace(
    workspace_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> MessageResponse:
    """Soft delete a workspace."""
    await soft_delete_workspace(session, user, workspace_id)
    return MessageResponse(message="Workspace deleted.")


@router.post(
    "/{workspace_id}/invites",
    response_model=WorkspaceInviteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Invite workspace member",
)
async def invite_workspace_member(
    workspace_id: UUID,
    payload: WorkspaceInviteRequest,
    _session: DatabaseSession,
    _user: CurrentUser,
) -> WorkspaceInviteResponse:
    """Prepare member invite structure for future email delivery."""
    return WorkspaceInviteResponse(
        accepted=True,
        message=f"Invite structure accepted for {payload.email} in workspace {workspace_id}.",
    )
