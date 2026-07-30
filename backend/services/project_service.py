"""Project service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.accounts import User
from models.project import Book, Project, ProjectSettings
from schemas.projects import (
    BookCreateRequest,
    ProjectCreateRequest,
    ProjectSettingsRequest,
    ProjectUpdateRequest,
)
from services.rbac_service import require_workspace_permission


async def list_projects(
    session: AsyncSession,
    user: User,
    workspace_id: UUID | None = None,
    search: str | None = None,
    status_filter: str | None = None,
    favorite: bool | None = None,
) -> list[Project]:
    """List visible projects with search/filter support."""
    statement = (
        select(Project).where(Project.deleted_at.is_(None)).order_by(Project.updated_at.desc())
    )
    if workspace_id is not None:
        await require_workspace_permission(session, user, workspace_id, "project:read")
        statement = statement.where(Project.workspace_id == workspace_id)
    else:
        statement = statement.where(Project.owner_user_id == user.id)
    if search:
        like = f"%{search}%"
        statement = statement.where(or_(Project.name.ilike(like), Project.title.ilike(like)))
    if status_filter:
        statement = statement.where(Project.status == status_filter)
    if favorite is not None:
        statement = statement.where(Project.is_favorite == favorite)

    result = await session.execute(statement)
    return list(result.scalars())


async def create_project(
    session: AsyncSession,
    user: User,
    payload: ProjectCreateRequest,
) -> Project:
    """Create a project with default settings."""
    await require_workspace_permission(session, user, payload.workspace_id, "project:create")
    project = Project(
        workspace_id=payload.workspace_id,
        owner_user_id=user.id,
        name=payload.name,
        title=payload.title or payload.name,
        description=payload.description,
        status="active",
    )
    session.add(project)
    await session.flush()
    settings_payload = payload.settings or ProjectSettingsRequest()
    session.add(
        ProjectSettings(project_id=project.id, **settings_payload.model_dump(exclude_none=True)),
    )
    await session.commit()
    await session.refresh(project)
    return project


async def get_project(session: AsyncSession, user: User, project_id: UUID) -> Project:
    """Return a project if visible to the current user."""
    project = await session.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    await require_workspace_permission(session, user, project.workspace_id, "project:read")
    return project


async def update_project(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    payload: ProjectUpdateRequest,
) -> Project:
    """Update project metadata."""
    project = await get_project(session, user, project_id)
    await require_workspace_permission(session, user, project.workspace_id, "project:update")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    await session.commit()
    await session.refresh(project)
    return project


async def soft_delete_project(session: AsyncSession, user: User, project_id: UUID) -> None:
    """Soft delete a project."""
    project = await get_project(session, user, project_id)
    await require_workspace_permission(session, user, project.workspace_id, "project:delete")
    project.deleted_at = datetime.now(UTC)
    project.status = "deleted"
    await session.commit()


async def archive_project(session: AsyncSession, user: User, project_id: UUID) -> Project:
    """Archive a project."""
    return await update_project(session, user, project_id, ProjectUpdateRequest(status="archived"))


async def duplicate_project(session: AsyncSession, user: User, project_id: UUID) -> Project:
    """Duplicate a project shell and its settings."""
    source = await get_project(session, user, project_id)
    await require_workspace_permission(session, user, source.workspace_id, "project:create")
    duplicate = Project(
        workspace_id=source.workspace_id,
        owner_user_id=user.id,
        name=f"{source.name} Copy",
        title=f"{source.title} Copy",
        description=source.description,
        status="active",
        metadata_json=source.metadata_json,
    )
    session.add(duplicate)
    await session.flush()
    settings = await get_project_settings(session, user, source.id)
    session.add(
        ProjectSettings(
            project_id=duplicate.id,
            book_size=settings.book_size,
            custom_book_size=settings.custom_book_size,
            margins=settings.margins,
            font=settings.font,
            theme=settings.theme,
            writing_language=settings.writing_language,
            image_ratio=settings.image_ratio,
            image_style=settings.image_style,
            image_color_theme=settings.image_color_theme,
            illustration_style=settings.illustration_style,
            image_quality=settings.image_quality,
            default_ai_provider=settings.default_ai_provider,
            preferred_ai_provider=settings.preferred_ai_provider,
            preferred_ai_model=settings.preferred_ai_model,
            ai_temperature=settings.ai_temperature,
            ai_max_tokens=settings.ai_max_tokens,
            writing_style=settings.writing_style,
            export_preferences=settings.export_preferences,
            kdp_options=settings.kdp_options,
        ),
    )
    await session.commit()
    await session.refresh(duplicate)
    return duplicate


async def get_project_settings(
    session: AsyncSession,
    user: User,
    project_id: UUID,
) -> ProjectSettings:
    """Return project settings."""
    project = await get_project(session, user, project_id)
    result = await session.execute(
        select(ProjectSettings).where(ProjectSettings.project_id == project.id),
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = ProjectSettings(project_id=project.id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


async def update_project_settings(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    payload: ProjectSettingsRequest,
) -> ProjectSettings:
    """Update project settings."""
    project = await get_project(session, user, project_id)
    await require_workspace_permission(session, user, project.workspace_id, "project:update")
    settings = await get_project_settings(session, user, project_id)
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(settings, key, value)
    await session.commit()
    await session.refresh(settings)
    return settings


async def create_book_legacy(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    payload: BookCreateRequest,
) -> Book:
    """DEPRECATED: kept for backward compatibility only.

    The canonical book-creation entry point is
    ``services.book_service.create_primary_book`` invoked from
    ``POST /projects/{project_id}/book`` (in ``api/v1/books.py``).

    This legacy implementation forwards to the canonical path.
    """
    from services.book_service import create_primary_book

    project = await get_project(session, user, project_id)
    return await create_primary_book(session, user, project, payload)


async def list_books(session: AsyncSession, user: User, project_id: UUID) -> list[Book]:
    """List books inside a project."""
    project = await get_project(session, user, project_id)
    result = await session.execute(
        select(Book)
        .where(Book.project_id == project.id, Book.deleted_at.is_(None))
        .order_by(Book.created_at),
    )
    return list(result.scalars())
