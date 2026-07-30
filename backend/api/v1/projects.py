"""Project and settings endpoints.

Book creation has a single canonical path: ``POST /projects/{project_id}/book``
in ``api/v1/books.py``. That endpoint atomically creates the Book, the linked
WritingBook, a default Chapter 1, and the editor state.
"""

from uuid import UUID

from fastapi import APIRouter, Query, status

from api.dependencies import CurrentUser, DatabaseSession
from schemas.auth import MessageResponse
from schemas.projects import (
    BookResponse,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectSettingsRequest,
    ProjectSettingsResponse,
    ProjectUpdateRequest,
)
from services.project_service import (
    archive_project,
    create_project,
    duplicate_project,
    get_project,
    get_project_settings,
    list_books,
    list_projects,
    soft_delete_project,
    update_project,
    update_project_settings,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse], summary="List projects")
async def get_projects(
    session: DatabaseSession,
    user: CurrentUser,
    workspace_id: UUID | None = None,
    search: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    favorite: bool | None = None,
) -> list[ProjectResponse]:
    """List projects with search, filter, sort-by-recency defaults, and favorites support."""
    projects = await list_projects(session, user, workspace_id, search, status_filter, favorite)
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get("/recent", response_model=list[ProjectResponse], summary="Recent projects")
async def get_recent_projects(session: DatabaseSession, user: CurrentUser) -> list[ProjectResponse]:
    """Return recent projects for the authenticated user."""
    projects = await list_projects(session, user)
    return [ProjectResponse.model_validate(project) for project in projects[:10]]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
)
async def post_project(
    payload: ProjectCreateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectResponse:
    """Create a project in a workspace."""
    project = await create_project(session, user, payload)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project")
async def get_project_endpoint(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectResponse:
    """Retrieve one project."""
    project = await get_project(session, user, project_id)
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse, summary="Update project")
@router.patch("/{project_id}", response_model=ProjectResponse, include_in_schema=False)
async def put_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectResponse:
    """Update project overview fields."""
    project = await update_project(session, user, project_id, payload)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", response_model=MessageResponse, summary="Delete project")
async def delete_project(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> MessageResponse:
    """Soft delete a project."""
    await soft_delete_project(session, user, project_id)
    return MessageResponse(message="Project deleted.")


@router.post("/{project_id}/archive", response_model=ProjectResponse, summary="Archive project")
async def post_archive_project(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectResponse:
    """Archive a project."""
    project = await archive_project(session, user, project_id)
    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/duplicate", response_model=ProjectResponse, summary="Duplicate project")
async def post_duplicate_project(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectResponse:
    """Duplicate a project shell and its settings."""
    project = await duplicate_project(session, user, project_id)
    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/favorite", response_model=ProjectResponse, summary="Favorite project")
async def post_favorite_project(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectResponse:
    """Mark a project as favorite."""
    project = await update_project(
        session,
        user,
        project_id,
        ProjectUpdateRequest(is_favorite=True),
    )
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}/favorite",
    response_model=ProjectResponse,
    summary="Unfavorite project",
)
async def delete_favorite_project(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectResponse:
    """Remove project from favorites."""
    project = await update_project(
        session,
        user,
        project_id,
        ProjectUpdateRequest(is_favorite=False),
    )
    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}/settings",
    response_model=ProjectSettingsResponse,
    summary="Get project settings",
)
async def get_settings_endpoint(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectSettingsResponse:
    """Retrieve project settings."""
    settings = await get_project_settings(session, user, project_id)
    return ProjectSettingsResponse.model_validate(settings)


@router.put(
    "/{project_id}/settings",
    response_model=ProjectSettingsResponse,
    summary="Update project settings",
)
async def put_settings_endpoint(
    project_id: UUID,
    payload: ProjectSettingsRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectSettingsResponse:
    """Update project settings."""
    settings = await update_project_settings(session, user, project_id, payload)
    return ProjectSettingsResponse.model_validate(settings)


@router.get(
    "/{project_id}/books",
    response_model=list[BookResponse],
    summary="List books in a project",
)
async def get_books(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[BookResponse]:
    """List books inside a project. Each book is fully initialized with a WritingBook."""
    books = await list_books(session, user, project_id)
    return [BookResponse.model_validate(book) for book in books]
