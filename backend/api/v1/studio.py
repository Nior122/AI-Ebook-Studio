"""Studio UX router — the API surface of the unified workspace.

Autosave, version snapshots + restore, activity timeline, notifications,
manuscript search, bookmarks, project stages, the in-workspace AI assistant,
per-user provider keys, image generation (Pollinations), and the live
WebSocket channel that streams progress/activity/notification events to the UI.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentUser, DatabaseSession
from core.exceptions import ResourceNotFoundError, ValidationAppError
from core.security import decode_access_token, verify_clerk_token
from database.session import AsyncSessionLocal
from models.accounts import User
from models.assets import ImageAsset
from models.studio import Bookmark, ProjectActivity, ProjectVersion, StudioNotification
from schemas.studio import (
    ActivityRead,
    AssistantRequest,
    AssistantResponse,
    AutosaveRequest,
    AutosaveResponse,
    BookmarkCreate,
    BookmarkRead,
    NotificationListResponse,
    NotificationRead,
    ProviderKeyRequest,
    ProviderKeyStatus,
    RestoreResponse,
    SearchResponse,
    STAGE_LABELS,
    StageResponse,
    StageUpdate,
    VersionCreate,
    VersionRead,
)
from services import project_service, studio_service
from services.events import bus, publish_project_event

router = APIRouter(tags=["studio"])

_ASPECT_DIMS = {
    "16:9": (1600, 900),
    "4:3": (1400, 1050),
    "square": (1024, 1024),
    "portrait": (900, 1600),
}


# ---------------------------------------------------------------------------
# Autosave
# ---------------------------------------------------------------------------
@router.put(
    "/projects/{project_id}/autosave",
    response_model=AutosaveResponse,
    summary="Bulk-autosave chapter edits",
)
async def autosave(
    project_id: UUID,
    payload: AutosaveRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> AutosaveResponse:
    """Persist debounced chapter content. Safe to call repeatedly."""
    saved, saved_at = await studio_service.autosave_project(
        session, user, project_id, payload.chapters
    )
    return AutosaveResponse(saved_at=saved_at, saved_chapters=saved, revision=saved)


# ---------------------------------------------------------------------------
# Versions (restore points)
# ---------------------------------------------------------------------------
@router.get(
    "/projects/{project_id}/versions",
    response_model=list[VersionRead],
    summary="List project restore points",
)
async def list_versions(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[VersionRead]:
    versions = await studio_service.list_versions(session, user, project_id, limit)
    return [
        VersionRead(
            id=v.id, project_id=v.project_id, label=v.label, reason=v.reason,
            created_by=v.created_by, created_at=v.created_at,
        )
        for v in versions
    ]


@router.post(
    "/projects/{project_id}/versions",
    response_model=VersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual restore point",
)
async def create_version(
    project_id: UUID,
    payload: VersionCreate,
    session: DatabaseSession,
    user: CurrentUser,
) -> VersionRead:
    version = await studio_service.create_version(
        session, user, project_id, payload.label, payload.reason
    )
    return VersionRead(
        id=version.id, project_id=version.project_id, label=version.label,
        reason=version.reason, created_by=version.created_by, created_at=version.created_at,
    )


@router.post(
    "/versions/{version_id}/restore",
    response_model=RestoreResponse,
    summary="Restore a project snapshot",
)
async def restore_version(
    version_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> RestoreResponse:
    updated, message = await studio_service.restore_version(session, user, version_id)
    return RestoreResponse(
        version_id=version_id, restored=True, chapters_updated=updated, message=message
    )


# ---------------------------------------------------------------------------
# Activity timeline
# ---------------------------------------------------------------------------
@router.get(
    "/projects/{project_id}/activities",
    response_model=list[ActivityRead],
    summary="Project activity timeline",
)
async def list_activities(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=300),
) -> list[ActivityRead]:
    activities = await studio_service.list_activities(session, user, project_id, limit)
    return [
        ActivityRead(
            id=a.id, project_id=a.project_id, kind=a.kind, message=a.message,
            meta=a.meta, created_at=a.created_at,
        )
        for a in activities
    ]


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="List my notifications",
)
async def list_notifications(
    session: DatabaseSession,
    user: CurrentUser,
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
) -> NotificationListResponse:
    items = await studio_service.list_notifications(
        session, user, limit=limit, unread_only=unread_only
    )
    unread = await studio_service.unread_notification_count(session, user)
    return NotificationListResponse(
        items=[
            NotificationRead(
                id=n.id, project_id=n.project_id, kind=n.kind, title=n.title, body=n.body,
                level=n.level, read_at=n.read_at, action_type=n.action_type,
                action_payload=n.action_payload, created_at=n.created_at,
            )
            for n in items
        ],
        unread=unread,
    )


@router.get(
    "/notifications/unread-count",
    response_model=dict[str, int],
    summary="Unread notification count",
)
async def unread_count(session: DatabaseSession, user: CurrentUser) -> dict[str, int]:
    return {"unread": await studio_service.unread_notification_count(session, user)}


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark a notification as read",
)
async def mark_read(
    notification_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> NotificationRead:
    notification = await studio_service.mark_notification_read(session, user, notification_id)
    if notification is None:
        raise ResourceNotFoundError("Notification not found.")
    return NotificationRead(
        id=notification.id, project_id=notification.project_id, kind=notification.kind,
        title=notification.title, body=notification.body, level=notification.level,
        read_at=notification.read_at, action_type=notification.action_type,
        action_payload=notification.action_payload, created_at=notification.created_at,
    )


@router.post(
    "/notifications/read-all",
    response_model=dict[str, int],
    summary="Mark all notifications as read",
)
async def mark_all_read(session: DatabaseSession, user: CurrentUser) -> dict[str, int]:
    return {"marked": await studio_service.mark_all_notifications_read(session, user)}


# ---------------------------------------------------------------------------
# Manuscript search
# ---------------------------------------------------------------------------
@router.get(
    "/projects/{project_id}/search",
    response_model=SearchResponse,
    summary="Search the manuscript",
)
async def search_project(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    q: str = Query(min_length=1, max_length=200),
) -> SearchResponse:
    results = await studio_service.search_project(session, user, project_id, q)
    return SearchResponse(query=q, results=results)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------
@router.get(
    "/projects/{project_id}/bookmarks",
    response_model=list[BookmarkRead],
    summary="List project bookmarks",
)
async def list_bookmarks(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[BookmarkRead]:
    bookmarks = await studio_service.list_bookmarks(session, user, project_id)
    return [
        BookmarkRead(
            id=b.id, project_id=b.project_id, chapter_id=b.chapter_id,
            title=b.title, note=b.note, created_at=b.created_at,
        )
        for b in bookmarks
    ]


@router.post(
    "/projects/{project_id}/bookmarks",
    response_model=BookmarkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a bookmark",
)
async def create_bookmark(
    project_id: UUID,
    payload: BookmarkCreate,
    session: DatabaseSession,
    user: CurrentUser,
) -> BookmarkRead:
    bookmark = await studio_service.create_bookmark(
        session, user, project_id, payload.title, payload.note, payload.chapter_id
    )
    return BookmarkRead(
        id=bookmark.id, project_id=bookmark.project_id, chapter_id=bookmark.chapter_id,
        title=bookmark.title, note=bookmark.note, created_at=bookmark.created_at,
    )


@router.delete(
    "/bookmarks/{bookmark_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a bookmark",
)
async def delete_bookmark(bookmark_id: UUID, session: DatabaseSession, user: CurrentUser):
    await studio_service.delete_bookmark(session, user, bookmark_id)


# ---------------------------------------------------------------------------
# Project lifecycle stage
# ---------------------------------------------------------------------------
@router.put(
    "/projects/{project_id}/stage",
    response_model=StageResponse,
    summary="Set the project lifecycle stage",
)
async def set_stage(
    project_id: UUID,
    payload: StageUpdate,
    session: DatabaseSession,
    user: CurrentUser,
) -> StageResponse:
    project = await studio_service.set_project_stage(session, user, project_id, payload.stage)
    return StageResponse(
        project_id=project.id, stage=project.stage,
        label=STAGE_LABELS.get(project.stage, project.stage),
    )


# ---------------------------------------------------------------------------
# AI assistant
# ---------------------------------------------------------------------------
@router.post(
    "/projects/{project_id}/assistant",
    response_model=AssistantResponse,
    summary="Chat with or edit via the in-workspace AI assistant",
)
async def assistant(
    project_id: UUID,
    payload: AssistantRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> AssistantResponse:
    result = await studio_service.run_assistant(
        session, user, project_id, payload.message,
        chapter_id=payload.chapter_id, action=payload.action,
    )
    return AssistantResponse(**result)


# ---------------------------------------------------------------------------
# Images (Pollinations — free, no key)
# ---------------------------------------------------------------------------
@router.get(
    "/projects/{project_id}/images",
    response_model=list[dict[str, Any]],
    summary="List generated images for a project",
)
async def list_images(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    project = await project_service.get_project(session, user, project_id)
    from services import book_service

    book = await book_service.get_primary_book_for_project(session, user, project)
    if book is None:
        return []
    result = await session.execute(
        select(ImageAsset)
        .where(ImageAsset.book_id == book.id)
        .order_by(ImageAsset.created_at.desc())
        .limit(60)
    )
    return [
        {
            "id": str(img.id),
            "chapter_id": str(img.chapter_id) if img.chapter_id else None,
            "prompt": img.prompt,
            "provider": img.provider,
            "aspect_ratio": img.aspect_ratio,
            "file_url": img.file_url,
            "status": img.status,
            "created_at": img.created_at,
        }
        for img in list(result.scalars())
    ]


@router.post(
    "/projects/{project_id}/images",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Generate an image with Pollinations",
)
async def generate_image(
    project_id: UUID,
    payload: dict[str, Any],
    session: DatabaseSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Generate an image for the book (Pollinations URL provider, no key needed)."""
    project = await project_service.get_project(session, user, project_id)
    from services import book_service

    book = await book_service.get_primary_book_for_project(session, user, project)
    if book is None:
        raise ValidationAppError("This project has no book yet — generate the book first.")

    prompt = str(payload.get("prompt") or "").strip()
    if len(prompt) < 8:
        raise ValidationAppError(
            "Image prompt is too short — describe the scene in at least a few words.",
            details={"hint": "Example: 'A cozy study with an open book and warm morning light'"},
        )
    aspect = str(payload.get("aspect_ratio") or "16:9")
    width, height = _ASPECT_DIMS.get(aspect, (1600, 900))
    style = str(payload.get("style") or "Photorealistic")
    chapter_id = payload.get("chapter_id")
    chapter_uuid = UUID(str(chapter_id)) if chapter_id else None

    from app.modules.images.providers.base import ImageGenerationRequest
    from app.modules.images.providers.pollinations_provider import PollinationsProvider

    result = await PollinationsProvider().generate_image(
        ImageGenerationRequest(
            prompt=prompt,
            negative_prompt=str(payload.get("negative_prompt") or ""),
            aspect_ratio=aspect,
            width=width,
            height=height,
            style=style,
            quality="high",
        )
    )
    image = ImageAsset(
        project_id=project.id,
        book_id=book.id,
        chapter_id=chapter_uuid,
        prompt=prompt,
        provider="pollinations",
        model=result.model,
        width=result.width,
        height=result.height,
        aspect_ratio=result.aspect_ratio,
        file_url=result.image_url,
        status="COMPLETED",
    )
    session.add(image)
    await session.commit()
    await session.refresh(image)

    await studio_service.record_activity(
        session, user.id, project.id, "image_generated",
        f"Image generated — {prompt[:60]}{'…' if len(prompt) > 60 else ''}",
        {"image_id": str(image.id)},
    )
    await studio_service.create_notification(
        session, user.id, project.id, "image_generated",
        "Image generated",
        "A new image is ready in the Images panel.",
        level="success", action_type="open_project", action_payload={"project_id": str(project.id)},
    )
    return {
        "id": str(image.id),
        "chapter_id": str(image.chapter_id) if image.chapter_id else None,
        "prompt": image.prompt,
        "file_url": image.file_url,
        "aspect_ratio": image.aspect_ratio,
        "status": image.status,
        "created_at": image.created_at,
    }


# ---------------------------------------------------------------------------
# Per-user AI provider keys
# ---------------------------------------------------------------------------
@router.get(
    "/settings/ai/key-status",
    response_model=ProviderKeyStatus,
    summary="Whether the user has a stored provider key",
)
async def key_status(session: DatabaseSession, user: CurrentUser) -> ProviderKeyStatus:
    return ProviderKeyStatus(**await studio_service.provider_key_status(session, user))


@router.put(
    "/settings/ai/key",
    response_model=ProviderKeyStatus,
    summary="Store an encrypted per-user AI provider key",
)
async def save_key(
    payload: ProviderKeyRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProviderKeyStatus:
    result = await studio_service.save_provider_key(
        session, user, payload.provider, payload.api_key
    )
    return ProviderKeyStatus(**result)


# ---------------------------------------------------------------------------
# Live WebSocket channel
# ---------------------------------------------------------------------------
async def _ws_user(token: str | None) -> User | None:
    """Resolve the authenticated user for a WebSocket connection."""
    from core.config import get_settings

    if not token:
        return None
    settings = get_settings()
    user_id: UUID | None = None
    if settings.clerk_jwks_url:
        try:
            payload = await verify_clerk_token(token, settings)
            clerk_id = payload.get("sub")
            if clerk_id:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(User).where(User.clerk_id == clerk_id)
                    )
                    user = result.scalar_one_or_none()
                    return user
        except Exception:
            return None
    try:
        user_id = decode_access_token(token, settings)
    except Exception:
        return None
    async with AsyncSessionLocal() as session:
        return await session.get(User, user_id)


@router.websocket("/ws/projects/{project_id}")
async def workspace_socket(websocket: WebSocket, project_id: UUID) -> None:
    """Stream live events for a project: progress, activities, notifications."""
    token = websocket.query_params.get("token")
    user = await _ws_user(token)
    if user is None:
        await websocket.close(code=4401)
        return

    async with AsyncSessionLocal() as session:
        try:
            project = await project_service.get_project(session, user, project_id)
        except Exception:
            project = None
    if project is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    project_channel = f"project:{project_id}"
    user_channel = f"user:{user.id}"
    project_queue = bus.subscribe(project_channel)
    user_queue = bus.subscribe(user_channel)
    try:
        await websocket.send_json({"type": "connected", "payload": {"project_id": str(project_id)}})
        while True:
            done, _ = await asyncio.wait(
                {asyncio.create_task(project_queue.get()), asyncio.create_task(user_queue.get())},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=25,
            )
            if done:
                for task in done:
                    try:
                        await websocket.send_text(task.result())
                    except Exception:
                        pass
            else:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        bus.unsubscribe(project_channel, project_queue)
        bus.unsubscribe(user_channel, user_queue)
