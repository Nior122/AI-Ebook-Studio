"""Studio UX service layer.

Business logic for the unified workspace: bulk autosave, project-level version
snapshots + restore, activity timeline, notifications, manuscript search,
bookmarks, project lifecycle stages, per-user AI provider keys, and the
in-workspace AI assistant.

Every function enforces ownership via :func:`project_service.get_project`
(User -> Workspace -> Project), so users can never touch another user's data.
"""

from __future__ import annotations

import base64
import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import ResourceNotFoundError, ValidationAppError
from models.accounts import User
from models.ai_provider_config import AIProviderPreference
from models.assets import BookSettings, ImageAsset
from models.book_writing import WritingBook, WritingChapter
from models.project import Book, Project
from models.studio import Bookmark, ProjectActivity, ProjectVersion, StudioNotification
from services import book_service, project_service
from services.ai_service import AIService
from services.events import publish_project_event, publish_user_event

PROJECT_STAGES = {"draft", "generating", "review", "ready_for_export", "published"}

STAGE_LABELS = {
    "draft": "Draft",
    "generating": "Generating",
    "review": "Review",
    "ready_for_export": "Ready for Export",
    "published": "Published",
}

# provider id -> Settings field that holds its API key
_PROVIDER_KEY_FIELDS = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "gemini": "google_api_key",
    "openrouter": "openrouter_api_key",
    "groq": "groq_api_key",
    "nvidia_nim": "nvidia_nim_api_key",
    "custom_openai": "custom_openai_api_key",
}


def _wc(text: str | None) -> int:
    return len(re.findall(r"\S+", text or ""))


async def _owned_project(session: AsyncSession, user: User, project_id: UUID) -> Project:
    return await project_service.get_project(session, user, project_id)


async def _primary_book(session: AsyncSession, user: User, project: Project) -> Book | None:
    return await book_service.get_primary_book_for_project(session, user, project)


async def _writing_book(session: AsyncSession, user: User, project: Project) -> WritingBook | None:
    """Resolve the WritingBook that belongs to this project (latest, title match first)."""
    result = await session.execute(
        select(WritingBook)
        .where(WritingBook.user_id == user.id, WritingBook.deleted_at.is_(None))
        .order_by(WritingBook.created_at.desc())
    )
    books = list(result.scalars())
    if not books:
        return None
    for book in books:
        if book.title == project.title:
            return book
    return books[0]


# ---------------------------------------------------------------------------
# Autosave
# ---------------------------------------------------------------------------
async def autosave_project(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    chapters: dict[str, str],
) -> tuple[int, datetime]:
    """Persist debounced chapter edits. Returns (saved_chapters, saved_at)."""
    project = await _owned_project(session, user, project_id)
    wb = await _writing_book(session, user, project)
    if wb is None:
        raise ValidationAppError(
            "This project has no writing book yet — generate the book first.",
            details={"hint": "Open the project and run Generate Book."},
        )
    if not chapters:
        return 0, datetime.now(UTC)

    ids = [UUID(str(cid)) for cid in chapters.keys()]
    result = await session.execute(
        select(WritingChapter).where(
            WritingChapter.book_id == wb.id,
            WritingChapter.id.in_(ids),
        )
    )
    rows = list(result.scalars())
    now = datetime.now(UTC)
    for chapter in rows:
        content = chapters.get(str(chapter.id), "")
        if content == chapter.content:
            continue
        chapter.content = content
        chapter.actual_word_count = _wc(content)
        chapter.status = "draft" if chapter.status in ("planned", "outlining") else chapter.status
        chapter.updated_at = now
    await session.commit()
    return len(rows), now


# ---------------------------------------------------------------------------
# Version snapshots + restore
# ---------------------------------------------------------------------------
async def _build_snapshot(
    session: AsyncSession,
    user: User,
    project: Project,
) -> dict[str, Any]:
    book = await _primary_book(session, user, project)
    wb = await _writing_book(session, user, project)

    settings: dict[str, Any] = {}
    if book is not None:
        bs = await session.execute(select(BookSettings).where(BookSettings.book_id == book.id))
        settings_row = bs.scalar_one_or_none()
        if settings_row is not None:
            settings = {
                "kdp_trim_size": settings_row.kdp_trim_size,
                "custom_format_enabled": settings_row.custom_format_enabled,
                "page_width": settings_row.page_width,
                "page_height": settings_row.page_height,
                "margin_top": settings_row.margin_top,
                "margin_bottom": settings_row.margin_bottom,
                "margin_left": settings_row.margin_left,
                "margin_right": settings_row.margin_right,
                "body_font": settings_row.body_font,
                "body_font_size": settings_row.body_font_size,
                "heading_font": settings_row.heading_font,
                "line_spacing": settings_row.line_spacing,
                "paragraph_spacing": settings_row.paragraph_spacing,
                "image_width": settings_row.image_width,
                "image_alignment": settings_row.image_alignment,
                "image_aspect_ratio": settings_row.image_aspect_ratio,
                "image_style": settings_row.image_style,
                "caption_enabled": settings_row.caption_enabled,
                "caption_font_size": settings_row.caption_font_size,
                "chapter_page_breaks": settings_row.chapter_page_breaks,
                "toc_enabled": settings_row.toc_enabled,
            }

    chapters: list[dict[str, Any]] = []
    if wb is not None:
        result = await session.execute(
            select(WritingChapter)
            .where(WritingChapter.book_id == wb.id)
            .order_by(WritingChapter.chapter_number)
        )
        for ch in list(result.scalars()):
            chapters.append(
                {
                    "id": str(ch.id),
                    "chapter_number": ch.chapter_number,
                    "title": ch.title,
                    "purpose": ch.purpose,
                    "objective": ch.objective,
                    "summary": ch.summary,
                    "outline": ch.outline,
                    "outline_sections": ch.outline_sections or [],
                    "content": ch.content,
                    "status": ch.status,
                    "target_word_count": ch.target_word_count,
                    "is_approved": ch.is_approved,
                }
            )

    return {
        "project": {
            "title": project.title,
            "description": project.description,
            "stage": project.stage,
        },
        "book": (
            {
                "title": book.title,
                "subtitle": book.subtitle,
                "author_name": book.author_name,
                "description": book.description,
                "language": book.language,
                "target_audience": book.target_audience,
                "writing_style": book.writing_style,
                "status": book.status,
            }
            if book is not None
            else {}
        ),
        "settings": settings,
        "chapters": chapters,
    }


async def create_version(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    label: str,
    reason: str | None = None,
    *,
    created_by: str = "manual",
    announce: bool = True,
) -> ProjectVersion:
    """Create a project restore point and record it on the timeline."""
    project = await _owned_project(session, user, project_id)
    version = ProjectVersion(
        project_id=project.id,
        user_id=user.id,
        label=label,
        reason=reason,
        snapshot=await _build_snapshot(session, user, project),
        created_by=created_by,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    if announce:
        await record_activity(
            session, user.id, project.id, "version_created",
            f"Version created — {label}", {"version_id": str(version.id)},
        )
    return version


async def list_versions(
    session: AsyncSession, user: User, project_id: UUID, limit: int = 50
) -> list[ProjectVersion]:
    project = await _owned_project(session, user, project_id)
    result = await session.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project.id)
        .order_by(ProjectVersion.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def restore_version(
    session: AsyncSession, user: User, version_id: UUID
) -> tuple[int, str]:
    """Restore a snapshot. Returns (chapters_updated, message)."""
    result = await session.execute(
        select(ProjectVersion).where(ProjectVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise ResourceNotFoundError("Version not found.")
    project = await _owned_project(session, user, version.project_id)

    # Protect the current state with an automatic restore point.
    await create_version(
        session, user, project.id,
        label=f"Before restoring '{version.label}'",
        reason="Automatic safety snapshot taken before restore.",
        created_by="auto",
        announce=False,
    )

    snapshot = version.snapshot
    book = await _primary_book(session, user, project)
    wb = await _writing_book(session, user, project)
    if wb is None:
        raise ValidationAppError("Cannot restore: this project has no writing book.")

    # --- project meta ---
    proj_data = snapshot.get("project") or {}
    if proj_data.get("title"):
        project.title = str(proj_data["title"])
    if "description" in proj_data:
        project.description = str(proj_data["description"]) if proj_data["description"] else None

    # --- book fields ---
    if book is not None:
        book_data = snapshot.get("book") or {}
        for field in ("title", "subtitle", "author_name", "description", "language",
                      "target_audience", "writing_style", "status"):
            if field in book_data and book_data[field] is not None:
                setattr(book, field, book_data[field])

    # --- settings ---
    settings_data = snapshot.get("settings") or {}
    if settings_data:
        bs_result = await session.execute(select(BookSettings).where(BookSettings.book_id == book.id))
        settings_row = bs_result.scalar_one_or_none()
        if settings_row is None and book is not None:
            settings_row = BookSettings(book_id=book.id)
            session.add(settings_row)
            await session.flush()
        for field, value in settings_data.items():
            if hasattr(settings_row, field):
                setattr(settings_row, field, value)

    # --- chapters ---
    existing_result = await session.execute(
        select(WritingChapter).where(WritingChapter.book_id == wb.id)
    )
    existing = {str(ch.id): ch for ch in list(existing_result.scalars())}
    next_number = max((ch.chapter_number for ch in existing.values()), default=0) + 1
    updated = 0
    for item in snapshot.get("chapters", []):
        chapter_id = str(item.get("id", ""))
        chapter = existing.get(chapter_id)
        if chapter is None:
            chapter = WritingChapter(
                book_id=wb.id,
                chapter_number=next_number,
                title=str(item.get("title") or "Untitled chapter"),
            )
            session.add(chapter)
            next_number += 1
        chapter.chapter_number = int(item.get("chapter_number") or chapter.chapter_number)
        chapter.title = str(item.get("title") or chapter.title)
        chapter.purpose = item.get("purpose")
        chapter.objective = item.get("objective")
        chapter.summary = item.get("summary")
        chapter.outline = item.get("outline")
        chapter.outline_sections = item.get("outline_sections") or []
        chapter.content = str(item.get("content") or "")
        chapter.status = str(item.get("status") or "draft")
        chapter.target_word_count = item.get("target_word_count")
        chapter.actual_word_count = _wc(chapter.content)
        chapter.is_approved = bool(item.get("is_approved"))
        updated += 1

    await session.commit()

    await record_activity(
        session, user.id, project.id, "version_restored",
        f"Restored version — {version.label}", {"version_id": str(version.id), "chapters": updated},
    )
    await create_notification(
        session, user.id, project.id, "version_restored",
        "Version restored",
        f"'{version.label}' is now the active manuscript ({updated} chapters).",
        level="success", action_type="open_project", action_payload={"project_id": str(project.id)},
    )
    publish_project_event(str(project.id), "version.restored", {
        "version_id": str(version.id), "chapters": updated,
    })
    return updated, f"Restored {updated} chapter(s) from '{version.label}'."


# ---------------------------------------------------------------------------
# Activity timeline
# ---------------------------------------------------------------------------
async def record_activity(
    session: AsyncSession,
    user_id: UUID | None,
    project_id: UUID,
    kind: str,
    message: str,
    meta: dict[str, Any] | None = None,
) -> ProjectActivity:
    """Persist a timeline entry and broadcast it live to the workspace."""
    activity = ProjectActivity(
        project_id=project_id,
        user_id=user_id,
        kind=kind,
        message=message,
        meta=meta or {},
    )
    session.add(activity)
    await session.commit()
    publish_project_event(str(project_id), "activity.created", {
        "id": str(activity.id), "kind": kind, "message": message, "meta": meta or {},
    })
    return activity


async def list_activities(
    session: AsyncSession, user: User, project_id: UUID, limit: int = 100
) -> list[ProjectActivity]:
    project = await _owned_project(session, user, project_id)
    result = await session.execute(
        select(ProjectActivity)
        .where(ProjectActivity.project_id == project.id)
        .order_by(ProjectActivity.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
async def create_notification(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID | None,
    kind: str,
    title: str,
    body: str | None = None,
    *,
    level: str = "info",
    action_type: str | None = None,
    action_payload: dict[str, Any] | None = None,
) -> StudioNotification:
    notification = StudioNotification(
        user_id=user_id,
        project_id=project_id,
        kind=kind,
        title=title,
        body=body,
        level=level,
        action_type=action_type,
        action_payload=action_payload,
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    publish_user_event(str(user_id), "notification.created", {
        "id": str(notification.id), "kind": kind, "title": title, "level": level,
        "project_id": str(project_id) if project_id else None,
    })
    if project_id is not None:
        publish_project_event(str(project_id), "notification.created", {
            "id": str(notification.id), "kind": kind, "title": title, "level": level,
        })
    return notification


async def list_notifications(
    session: AsyncSession,
    user: User,
    *,
    limit: int = 50,
    unread_only: bool = False,
) -> list[StudioNotification]:
    query = select(StudioNotification).where(
        StudioNotification.user_id == user.id,
        StudioNotification.deleted_at.is_(None),
    )
    if unread_only:
        query = query.where(StudioNotification.read_at.is_(None))
    query = query.order_by(StudioNotification.created_at.desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars())


async def unread_notification_count(session: AsyncSession, user: User) -> int:
    result = await session.execute(
        select(StudioNotification).where(
            StudioNotification.user_id == user.id,
            StudioNotification.read_at.is_(None),
            StudioNotification.deleted_at.is_(None),
        )
    )
    return len(list(result.scalars()))


async def mark_notification_read(
    session: AsyncSession, user: User, notification_id: UUID
) -> StudioNotification | None:
    result = await session.execute(
        select(StudioNotification).where(
            StudioNotification.id == notification_id,
            StudioNotification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is not None and notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await session.commit()
    return notification


async def mark_all_notifications_read(session: AsyncSession, user: User) -> int:
    result = await session.execute(
        select(StudioNotification).where(
            StudioNotification.user_id == user.id,
            StudioNotification.read_at.is_(None),
            StudioNotification.deleted_at.is_(None),
        )
    )
    notifications = list(result.scalars())
    now = datetime.now(UTC)
    for notification in notifications:
        notification.read_at = now
    await session.commit()
    return len(notifications)


# ---------------------------------------------------------------------------
# Manuscript search
# ---------------------------------------------------------------------------
async def search_project(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    query: str,
) -> list[dict[str, Any]]:
    """Search chapters, headings, and image captions. Returns result dicts."""
    project = await _owned_project(session, user, project_id)
    wb = await _writing_book(session, user, project)
    q = query.strip().lower()
    if not q:
        return []
    needle = f"%{q}%"
    results: list[dict[str, Any]] = []

    if wb is not None:
        chapter_result = await session.execute(
            select(WritingChapter)
            .where(
                WritingChapter.book_id == wb.id,
                or_(WritingChapter.content.ilike(needle), WritingChapter.title.ilike(needle)),
            )
            .order_by(WritingChapter.chapter_number)
            .limit(10)
        )
        for ch in list(chapter_result.scalars()):
            text = ch.content or ""
            idx = text.lower().find(q)
            snippet = ""
            if idx >= 0:
                snippet = text[max(0, idx - 60): idx + 160].replace("\n", " ").strip()
            else:
                snippet = text[:160].replace("\n", " ").strip()
            results.append({
                "type": "chapter",
                "chapter_id": str(ch.id),
                "chapter_title": ch.title,
                "snippet": snippet or ch.title,
            })
            # Heading hits inside this chapter (max 3).
            heading_hits = 0
            for line in (text.splitlines() or []):
                m = re.match(r"^(#{1,3})\s+(.+)$", line.strip())
                if m and q in line.lower():
                    results.append({
                        "type": "heading",
                        "chapter_id": str(ch.id),
                        "chapter_title": ch.title,
                        "snippet": f"#{'#' * len(m.group(1))} {m.group(2)}",
                        "heading": m.group(2).strip(),
                    })
                    heading_hits += 1
                    if heading_hits >= 3:
                        break

    book = await _primary_book(session, user, project)
    if book is not None:
        image_result = await session.execute(
            select(ImageAsset)
            .where(ImageAsset.book_id == book.id, ImageAsset.prompt.ilike(needle))
            .order_by(ImageAsset.created_at.desc())
            .limit(10)
        )
        for img in list(image_result.scalars()):
            results.append({
                "type": "image_caption",
                "chapter_id": str(img.chapter_id) if img.chapter_id else None,
                "chapter_title": "Images",
                "snippet": (img.prompt or "")[:200],
                "image_url": img.file_url,
            })

    return results[:30]


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------
async def list_bookmarks(
    session: AsyncSession, user: User, project_id: UUID
) -> list[Bookmark]:
    project = await _owned_project(session, user, project_id)
    result = await session.execute(
        select(Bookmark)
        .where(Bookmark.project_id == project.id, Bookmark.user_id == user.id)
        .order_by(Bookmark.created_at.desc())
    )
    return list(result.scalars())


async def create_bookmark(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    title: str,
    note: str | None = None,
    chapter_id: UUID | None = None,
) -> Bookmark:
    project = await _owned_project(session, user, project_id)
    bookmark = Bookmark(
        project_id=project.id, user_id=user.id,
        chapter_id=chapter_id, title=title, note=note,
    )
    session.add(bookmark)
    await session.commit()
    await session.refresh(bookmark)
    return bookmark


async def delete_bookmark(
    session: AsyncSession, user: User, bookmark_id: UUID
) -> None:
    result = await session.execute(
        select(Bookmark).where(Bookmark.id == bookmark_id, Bookmark.user_id == user.id)
    )
    bookmark = result.scalar_one_or_none()
    if bookmark is None:
        raise ResourceNotFoundError("Bookmark not found.")
    await session.delete(bookmark)
    await session.commit()


# ---------------------------------------------------------------------------
# Project lifecycle stage
# ---------------------------------------------------------------------------
async def set_project_stage(
    session: AsyncSession, user: User, project_id: UUID, stage: str
) -> Project:
    if stage not in PROJECT_STAGES:
        raise ValidationAppError(
            f"Unknown stage '{stage}'. Valid stages: {', '.join(sorted(PROJECT_STAGES))}."
        )
    project = await _owned_project(session, user, project_id)
    previous = project.stage or "draft"
    project.stage = stage
    project.updated_at = datetime.now(UTC)
    await session.commit()
    await record_activity(
        session, user.id, project.id, "stage_changed",
        f"Project stage: {STAGE_LABELS.get(previous, previous)} → {STAGE_LABELS.get(stage, stage)}",
        {"from": previous, "to": stage},
    )
    if stage in ("ready_for_export", "published"):
        await create_notification(
            session, user.id, project.id, "stage_changed",
            f"Project is now {STAGE_LABELS.get(stage, stage)}",
            None, level="success", action_type="open_project",
            action_payload={"project_id": str(project.id)},
        )
    publish_project_event(str(project.id), "stage.changed", {"stage": stage})
    return project


# ---------------------------------------------------------------------------
# Per-user AI provider keys (encrypted at rest)
# ---------------------------------------------------------------------------
def _fernet() -> Fernet:
    settings = get_settings()
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest())
    return Fernet(key)


async def save_provider_key(
    session: AsyncSession, user: User, provider: str, api_key: str
) -> dict[str, Any]:
    from providers.ai.registry import ProviderRegistry

    registry = ProviderRegistry()
    registry.load_from_settings(get_settings())
    if provider not in _PROVIDER_KEY_FIELDS:
        raise ValidationAppError(
            f"Unknown AI provider '{provider}'. Supported: {', '.join(sorted(_PROVIDER_KEY_FIELDS))}"
        )
    if provider not in registry.list():
        raise ValidationAppError(f"AI provider '{provider}' is not registered.")

    encrypted = _fernet().encrypt(api_key.encode()).decode()
    result = await session.execute(
        select(AIProviderPreference).where(AIProviderPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs is None:
        prefs = AIProviderPreference(user_id=user.id)
        session.add(prefs)
    prefs.uses_custom_key = True
    prefs.encrypted_api_key = encrypted
    prefs.key_provider = provider
    prefs.preferred_provider = provider
    await session.commit()
    return {"provider": provider, "has_key": True}


async def provider_key_status(session: AsyncSession, user: User) -> dict[str, Any]:
    result = await session.execute(
        select(AIProviderPreference).where(AIProviderPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs is None or not prefs.uses_custom_key or not prefs.encrypted_api_key:
        return {"provider": None, "has_key": False}
    return {"provider": prefs.key_provider, "has_key": True}


async def build_ai_service_for_user(session: AsyncSession, user: User) -> AIService:
    """AIService honouring the user's stored provider key, else global config."""
    result = await session.execute(
        select(AIProviderPreference).where(AIProviderPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs is not None and prefs.uses_custom_key and prefs.encrypted_api_key and prefs.key_provider:
        try:
            key = _fernet().decrypt(prefs.encrypted_api_key.encode()).decode()
        except InvalidToken:
            key = None
        field = _PROVIDER_KEY_FIELDS.get(prefs.key_provider)
        if key and field:
            settings = get_settings().model_copy(update={field: key})
            return AIService(settings=settings)
    return AIService()


# ---------------------------------------------------------------------------
# In-workspace AI assistant
# ---------------------------------------------------------------------------
async def run_assistant(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    message: str,
    chapter_id: UUID | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    """Chat with (or apply an edit via) the assistant for the current book."""
    project = await _owned_project(session, user, project_id)
    book = await _primary_book(session, user, project)
    wb = await _writing_book(session, user, project)

    chapter = None
    if chapter_id is not None and wb is not None:
        result = await session.execute(
            select(WritingChapter).where(
                WritingChapter.id == chapter_id, WritingChapter.book_id == wb.id
            )
        )
        chapter = result.scalar_one_or_none()

    book_context = (
        f"Title: {book.title}\n"
        f"Subtitle: {book.subtitle or ''}\n"
        f"Topic: {book.description or ''}\n"
        f"Audience: {book.target_audience or ''}\n"
        f"Style: {book.writing_style or ''}\n"
        f"Language: {book.language or 'en'}"
        if book is not None
        else f"Title: {project.title}"
    )

    if action in ("rewrite", "continue", "expand", "shorten", "fix_grammar"):
        if chapter is None:
            raise ValidationAppError(
                "This action needs an open chapter — select a chapter first.",
                details={"hint": "Click a chapter in the left panel, then retry."},
            )
        system = (
            "You are the writing assistant inside AI Ebook Studio. "
            f"ACTION: {action}. Return ONLY the updated full chapter content in "
            "markdown — no preamble, no commentary, no code fences. Preserve the "
            f"book's voice: audience '{book.target_audience or ''}', style '{book.writing_style or ''}'."
        )
        user_prompt = (
            f"BOOK CONTEXT:\n{book_context}\n\n"
            f"CHAPTER CONTENT:\n<<<{chapter.content}>>>\n\n"
            f"REQUEST: {message}"
        )
        response = await (await build_ai_service_for_user(session, user)).generate_text(
            system_prompt=system,
            user_prompt=user_prompt,
            task="assistant_edit",
            temperature=0.7,
        )
        new_content = (response.text or "").strip()
        return {
            "reply": f"{action.replace('_', ' ').title()} applied to '{chapter.title}'.",
            "applied": True,
            "new_content": new_content,
        }

    system = (
        "You are the AI assistant inside AI Ebook Studio. Answer the author's "
        "question about their book. Be concrete, cite the book's own content when "
        "relevant, and suggest actionable next steps. Keep replies under 250 words."
    )
    user_prompt = (
        f"BOOK CONTEXT:\n{book_context}\n"
        f"CURRENT CHAPTER: {chapter.title if chapter else '(none selected)'}\n"
        f"CHAPTER PREVIEW:\n{chapter.content[:1200] if chapter else ''}\n\n"
        f"QUESTION: {message}"
    )
    response = await (await build_ai_service_for_user(session, user)).generate_text(
        system_prompt=system,
        user_prompt=user_prompt,
        task="assistant_chat",
        temperature=0.6,
    )
    return {"reply": response.text or "…", "applied": False, "new_content": None}
