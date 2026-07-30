"""Phase 7 — AI editing service layer.

Encapsulates all editing business logic and enforces ownership on every
operation. Suggestion rows are never deleted — they move through state
transitions. Accepting a suggestion applies it to the chapter content and
creates a new immutable ChapterVersion so the author can always restore.

Ownership chain: User → Book (bw_books) → Chapter (bw_chapters) → Suggestion.
Every endpoint transitively verifies the owning user via _get_book / _get_chapter.
"""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, ResourceNotFoundError, ServiceUnavailableError
from models.accounts import User
from models.book_writing import (
    WritingBook as Book,
    WritingChapter as Chapter,
    ChapterVersion,
)
from models.editing import (
    EditingSession,
    EditingSuggestion,
    ReviewJob,
    SuggestionBatch,
)
from providers.ai.base import AIProviderError
from schemas.editing import (
    ReviewRequest,
    SelectionActionRequest,
    SuggestionCategory,
    SuggestionSeverity,
    SuggestionStatus,
    StartFullReviewRequest,
)
from services.ai_service import AIService, get_ai_service

from .engine import EditingEngine

# ---------------------------------------------------------------------------
# Ownership helpers
# ---------------------------------------------------------------------------
async def _get_book(session: AsyncSession, user: User, book_id: UUID) -> Book:
    book = await session.get(Book, book_id)
    if book is None or book.deleted_at is not None or book.user_id != user.id:
        raise ResourceNotFoundError("Book not found.")
    return book


async def _get_chapter(session: AsyncSession, user: User, chapter_id: UUID) -> Chapter:
    chapter = await session.get(Chapter, chapter_id)
    if chapter is None or chapter.deleted_at is not None:
        raise ResourceNotFoundError("Chapter not found.")
    await _get_book(session, user, chapter.book_id)
    return chapter


async def _get_suggestion(session: AsyncSession, user: User, suggestion_id: UUID) -> EditingSuggestion:
    sug = await session.get(EditingSuggestion, suggestion_id)
    if sug is None or sug.deleted_at is not None:
        raise ResourceNotFoundError("Suggestion not found.")
    await _get_chapter(session, user, sug.chapter_id)
    return sug


# ---------------------------------------------------------------------------
# AI guard
# ---------------------------------------------------------------------------
def _engine() -> EditingEngine:
    ai: AIService = get_ai_service()
    return EditingEngine(ai)


@asynccontextmanager
async def _ai_guard():
    try:
        yield
    except AIProviderError as exc:
        raise ServiceUnavailableError(
            "AI editing failed. Your existing manuscript content was not changed.",
            details={"provider_error": str(exc)},
        ) from exc


# ---------------------------------------------------------------------------
# Review — chapter / selection
# ---------------------------------------------------------------------------
async def review_chapter(
    session: AsyncSession,
    user: User,
    chapter_id: UUID,
    payload: ReviewRequest,
) -> dict[str, Any]:
    """Run an AI review on a chapter (or within selected_text), persist the session
    + suggestions, and return the session + suggestions list."""
    chapter = await _get_chapter(session, user, chapter_id)
    book = await _get_book(session, user, chapter.book_id)
    eng = _engine()

    async with _ai_guard():
        raw_suggestions = await eng.review_text(
            session, book, chapter,
            mode=payload.mode,
            selected_text=payload.selected_text,
            provider=payload.provider,
            model=payload.model,
            user_id=user.id,
            instruction=payload.instruction,
        )

    editing_session = EditingSession(
        book_id=book.id,
        chapter_id=chapter.id,
        user_id=user.id,
        mode=payload.mode,
        status="completed",
        completed_at=datetime.now(UTC),
    )
    session.add(editing_session)
    await session.flush()

    batch = SuggestionBatch(
        chapter_id=chapter.id,
        session_id=editing_session.id,
        label=payload.mode,
    )
    session.add(batch)
    await session.flush()

    suggestions: list[EditingSuggestion] = []
    for raw in raw_suggestions:
        if not raw.get("original_text") or not raw.get("category"):
            continue
        sug = EditingSuggestion(
            chapter_id=chapter.id,
            session_id=editing_session.id,
            batch_id=batch.id,
            category=raw["category"],
            severity=raw.get("severity", "low"),
            confidence=raw.get("confidence", 0.5),
            original_text=raw["original_text"],
            suggested_text=raw.get("suggested_text"),
            explanation=raw.get("explanation"),
            location_data=_build_location(chapter.content, raw["original_text"]),
            status="pending",
        )
        session.add(sug)
        suggestions.append(sug)

    await session.commit()
    await session.refresh(editing_session)
    for sug in suggestions:
        await session.refresh(sug)
    return {
        "session": editing_session,
        "suggestions": suggestions,
    }


async def act_on_selection(
    session: AsyncSession,
    user: User,
    chapter_id: UUID,
    payload: SelectionActionRequest,
) -> dict[str, Any]:
    """Rewrite/improve/proofread a *selected* text passage → returns one suggestion.

    The suggestion is immediately in 'accepted' state so the chapter content
    is updated and a version is created. This is a 'quick action' pattern:
    user selects text, picks an action, the AI fixes it, the result is applied.
    """
    chapter = await _get_chapter(session, user, chapter_id)
    book = await _get_book(session, user, chapter.book_id)
    eng = _engine()

    async with _ai_guard():
        raw = await eng.act_on_selection(
            session, book, chapter,
            action=payload.action,
            selected_text=payload.selected_text,
            provider=payload.provider,
            model=payload.model,
            user_id=user.id,
            instruction=payload.instruction,
        )

    editing_session = EditingSession(
        book_id=book.id, chapter_id=chapter.id, user_id=user.id,
        mode="selection_action", status="completed",
        completed_at=datetime.now(UTC),
    )
    session.add(editing_session)
    await session.flush()

    batch = SuggestionBatch(chapter_id=chapter.id, session_id=editing_session.id, label=payload.action)
    session.add(batch)
    await session.flush()

    sug = EditingSuggestion(
        chapter_id=chapter.id, session_id=editing_session.id, batch_id=batch.id,
        category=raw["category"], severity=raw.get("severity", "low"),
        confidence=raw.get("confidence", 0.6),
        original_text=payload.selected_text,
        suggested_text=raw["suggested_text"],
        explanation=raw.get("explanation"),
        location_data=_build_location(chapter.content, payload.selected_text),
        status="accepted",
        accepted_at=datetime.now(UTC),
    )
    session.add(sug)
    await session.flush()

    new_content = _apply_suggestion(chapter.content, sug)
    await _save_versioned_chapter(session, chapter, new_content,
                                   version_type="ai_edited",
                                   metadata={"action": payload.action, "suggestion_id": str(sug.id)},
                                   user_id=user.id)
    await session.commit()
    await session.refresh(sug)
    await session.refresh(chapter)
    return {"suggestion": sug, "chapter": chapter}


# ---------------------------------------------------------------------------
# Suggestions — list, get, accept, reject, ignore, regenerate
# ---------------------------------------------------------------------------
async def list_suggestions(
    session: AsyncSession,
    user: User,
    chapter_id: UUID,
    *,
    category: str | None = None,
    severity: str | None = None,
    status: str | None = None,
) -> list[EditingSuggestion]:
    await _get_chapter(session, user, chapter_id)
    stmt = select(EditingSuggestion).where(
        EditingSuggestion.chapter_id == chapter_id,
        EditingSuggestion.deleted_at.is_(None),
    )
    if category:
        stmt = stmt.where(EditingSuggestion.category == category)
    if severity:
        stmt = stmt.where(EditingSuggestion.severity == severity)
    if status:
        stmt = stmt.where(EditingSuggestion.status == status)
    stmt = stmt.order_by(EditingSuggestion.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_suggestion(
    session: AsyncSession, user: User, suggestion_id: UUID,
) -> EditingSuggestion:
    return await _get_suggestion(session, user, suggestion_id)


async def accept_suggestion(
    session: AsyncSession, user: User, suggestion_id: UUID,
) -> dict[str, Any]:
    sug = await _get_suggestion(session, user, suggestion_id)
    if sug.status not in ("pending", "ignored"):
        raise ConflictError("Suggestion has already been accepted or rejected.")
    chapter = await _get_chapter(session, user, sug.chapter_id)

    new_content = _apply_suggestion(chapter.content, sug)
    await _save_versioned_chapter(session, chapter, new_content,
                                   version_type="ai_edited",
                                   metadata={"accepted_suggestion_id": str(sug.id)},
                                   user_id=user.id)

    sug.status = "accepted"
    sug.accepted_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(chapter)
    await session.refresh(sug)
    return {"suggestion": sug, "chapter": chapter}


async def reject_suggestion(
    session: AsyncSession, user: User, suggestion_id: UUID,
    reason: str | None = None,
) -> EditingSuggestion:
    sug = await _get_suggestion(session, user, suggestion_id)
    if sug.status not in ("pending", "ignored"):
        raise ConflictError("Suggestion has already been accepted or rejected.")
    sug.status = "rejected"
    sug.rejected_at = datetime.now(UTC)
    if reason:
        sug.explanation = (sug.explanation or "") + f"\n[Rejected: {reason}]"
    await session.commit()
    await session.refresh(sug)
    return sug


async def ignore_suggestion(
    session: AsyncSession, user: User, suggestion_id: UUID,
) -> EditingSuggestion:
    sug = await _get_suggestion(session, user, suggestion_id)
    if sug.status not in ("pending",):
        raise ConflictError("Only pending suggestions can be ignored.")
    sug.status = "ignored"
    sug.ignored_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(sug)
    return sug


async def regenerate_suggestion(
    session: AsyncSession, user: User, suggestion_id: UUID,
) -> EditingSuggestion:
    """Mark a suggestion for regeneration. Creates a new batch relationship."""
    sug = await _get_suggestion(session, user, suggestion_id)
    chapter = await _get_chapter(session, user, sug.chapter_id)
    book = await _get_book(session, user, chapter.book_id)
    eng = _engine()

    async with _ai_guard():
        raw = await eng.act_on_selection(
            session, book, chapter,
            action="rewrite",
            selected_text=sug.original_text,
            user_id=user.id,
            instruction="Regenerate the suggestion for this text. Provide a fresh alternative.",
        )

    new_batch = SuggestionBatch(chapter_id=chapter.id, session_id=sug.session_id,
                                 label="regenerated", superseded_by_batch_id=sug.batch_id)
    session.add(new_batch)
    await session.flush()

    new_sug = EditingSuggestion(
        chapter_id=chapter.id, session_id=sug.session_id,
        batch_id=new_batch.id,
        category=sug.category, severity=sug.severity,
        confidence=raw.get("confidence", 0.6),
        original_text=sug.original_text,
        suggested_text=raw["suggested_text"],
        explanation=raw.get("explanation", f"Regenerated from suggestion {sug.id}"),
        location_data=sug.location_data,
        status="pending",
    )
    session.add(new_sug)
    # Mark old as ignored so the UI shows only the new one.
    sug.status = "ignored"
    sug.ignored_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(new_sug)
    return new_sug


# ---------------------------------------------------------------------------
# Bulk actions
# ---------------------------------------------------------------------------
async def accept_all(
    session: AsyncSession, user: User, chapter_id: UUID,
) -> dict[str, Any]:
    chapter = await _get_chapter(session, user, chapter_id)
    stmt = select(EditingSuggestion).where(
        EditingSuggestion.chapter_id == chapter_id,
        EditingSuggestion.deleted_at.is_(None),
        EditingSuggestion.status == "pending",
    )
    result = await session.execute(stmt)
    pending = list(result.scalars().all())
    if not pending:
        return {"updated": 0, "chapter_version_created": False, "chapter_id": chapter_id}

    content = chapter.content
    for sug in pending:
        content = _apply_suggestion(content, sug)
        sug.status = "accepted"
        sug.accepted_at = datetime.now(UTC)

    await _save_versioned_chapter(session, chapter, content,
                                   version_type="ai_edited",
                                   metadata={"accepted_suggestion_ids": [str(s.id) for s in pending]},
                                   user_id=user.id)
    await session.commit()
    await session.refresh(chapter)
    return {"updated": len(pending), "chapter_version_created": True, "chapter_id": chapter_id}


async def reject_all(
    session: AsyncSession, user: User, chapter_id: UUID,
) -> dict[str, Any]:
    chapter = await _get_chapter(session, user, chapter_id)
    stmt = select(EditingSuggestion).where(
        EditingSuggestion.chapter_id == chapter_id,
        EditingSuggestion.deleted_at.is_(None),
        EditingSuggestion.status == "pending",
    )
    result = await session.execute(stmt)
    pending = list(result.scalars().all())
    updated = 0
    for sug in pending:
        sug.status = "rejected"
        sug.rejected_at = datetime.now(UTC)
        updated += 1
    await session.commit()
    return {"updated": updated, "chapter_version_created": False, "chapter_id": chapter_id}


# ---------------------------------------------------------------------------
# Review summary
# ---------------------------------------------------------------------------
async def review_summary(
    session: AsyncSession, user: User, chapter_id: UUID,
) -> dict[str, Any]:
    await _get_chapter(session, user, chapter_id)

    total_result = await session.execute(
        select(func.count()).where(
            EditingSuggestion.chapter_id == chapter_id,
            EditingSuggestion.deleted_at.is_(None),
        ),
    )
    total = total_result.scalar() or 0

    cat_result = await session.execute(
        select(EditingSuggestion.category, func.count()).where(
            EditingSuggestion.chapter_id == chapter_id,
            EditingSuggestion.deleted_at.is_(None),
        ).group_by(EditingSuggestion.category),
    )
    by_category = {row[0]: row[1] for row in cat_result.all()}

    sev_result = await session.execute(
        select(EditingSuggestion.severity, func.count()).where(
            EditingSuggestion.chapter_id == chapter_id,
            EditingSuggestion.deleted_at.is_(None),
        ).group_by(EditingSuggestion.severity),
    )
    by_severity = {row[0]: row[1] for row in sev_result.all()}

    status_result = await session.execute(
        select(EditingSuggestion.status, func.count()).where(
            EditingSuggestion.chapter_id == chapter_id,
            EditingSuggestion.deleted_at.is_(None),
        ).group_by(EditingSuggestion.status),
    )
    by_status = {row[0]: row[1] for row in status_result.all()}

    return {
        "total": total,
        "by_category": by_category,
        "by_severity": by_severity,
        "by_status": by_status,
        "high_severity": by_severity.get("high", 0),
        "accepted": by_status.get("accepted", 0),
        "rejected": by_status.get("rejected", 0),
        "pending": by_status.get("pending", 0),
        "ignored": by_status.get("ignored", 0),
    }


# ---------------------------------------------------------------------------
# Review Job (full manuscript batch)
# ---------------------------------------------------------------------------
async def start_full_review(
    session: AsyncSession, user: User, book_id: UUID, payload: StartFullReviewRequest,
) -> ReviewJob:
    book = await _get_book(session, user, book_id)
    chapters_result = await session.execute(
        select(Chapter).where(
            Chapter.book_id == book_id,
            Chapter.deleted_at.is_(None),
        ).order_by(Chapter.chapter_number),
    )
    chapters = chapters_result.scalars().all()

    if payload.chapter_ids:
        chapters = [c for c in chapters if c.id in payload.chapter_ids]
    if not chapters:
        raise ResourceNotFoundError("No chapters found to review.")

    job = ReviewJob(
        book_id=book_id, user_id=user.id, chapter_id=None,
        mode=payload.mode, status="queued",
        total_items=len(chapters), processed_items=0, progress=0.0,
        progress_data=_initial_progress_data(chapters),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def process_review_job(
    session: AsyncSession,
    user: User,
    job_id: UUID,
) -> ReviewJob:
    """Process one chapter in a queued/processing full-manuscript review job.

    Call this repeatedly until status is 'completed' or 'failed'. Designed so a
    background scheduler can poll it; returns the job with updated progress.
    """
    job = await session.get(ReviewJob, job_id)
    if job is None:
        raise ResourceNotFoundError("Review job not found.")
    if job.user_id != user.id:
        raise ResourceNotFoundError("Review job not found.")
    if job.status in ("completed", "failed", "cancelled"):
        return job

    book = await _get_book(session, user, job.book_id)
    progress_data: list[dict] = job.progress_data or []
    if not progress_data:
        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        await session.commit()
        return job

    # Find the next unprocessed chapter in progress_data.
    next_entry = None
    next_idx = 0
    for i, entry in enumerate(progress_data):
        if entry.get("status") in ("queued", "processing"):
            next_entry = entry
            next_idx = i
            break
    if next_entry is None:
        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        job.progress = 1.0
        await session.commit()
        return job

    chapter_id = UUID(next_entry["chapter_id"])
    chapter = await _get_chapter(session, user, chapter_id)
    eng = _engine()

    job.status = "processing"
    progress_data[next_idx]["status"] = "processing"
    job.progress_data = progress_data
    await session.commit()

    try:
        async with _ai_guard():
            raw_suggestions = await eng.review_text(
                session, book, chapter,
                mode=job.mode,
                provider=None, model=None,
                user_id=user.id,
            )
    except ServiceUnavailableError as exc:
        job.status = "failed"
        job.error = str(exc)
        job.failed_at = datetime.now(UTC)
        progress_data[next_idx]["status"] = "failed"
        job.progress_data = progress_data
        await session.commit()
        return job

    job.status = "saving_suggestions"
    await session.commit()

    es = EditingSession(
        book_id=book.id, chapter_id=chapter.id, user_id=user.id,
        mode=job.mode, status="completed", completed_at=datetime.now(UTC),
    )
    session.add(es)
    await session.flush()

    batch = SuggestionBatch(chapter_id=chapter.id, session_id=es.id, label=f"review_job_{job.id}")
    session.add(batch)
    await session.flush()

    count = 0
    for raw in raw_suggestions:
        if not raw.get("original_text") or not raw.get("category"):
            continue
        sug = EditingSuggestion(
            chapter_id=chapter.id, session_id=es.id, batch_id=batch.id,
            category=raw["category"], severity=raw.get("severity", "low"),
            confidence=raw.get("confidence", 0.5),
            original_text=raw["original_text"],
            suggested_text=raw.get("suggested_text"),
            explanation=raw.get("explanation"),
            location_data=_build_location(chapter.content, raw["original_text"]),
            status="pending",
        )
        session.add(sug)
        count += 1

    job.processed_items += 1
    job.progress = job.processed_items / job.total_items if job.total_items else 0
    progress_data[next_idx]["status"] = "completed"
    progress_data[next_idx]["suggestion_count"] = count
    job.progress_data = progress_data

    remaining = [e for e in progress_data if e.get("status") in ("queued",)]
    if not remaining:
        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        job.progress = 1.0
    else:
        job.status = "queued"

    await session.commit()
    await session.refresh(job)
    return job


async def get_review_job(
    session: AsyncSession, user: User, job_id: UUID,
) -> ReviewJob:
    job = await session.get(ReviewJob, job_id)
    if job is None or job.user_id != user.id:
        raise ResourceNotFoundError("Review job not found.")
    return job


async def list_review_jobs(
    session: AsyncSession, user: User, book_id: UUID,
) -> list[ReviewJob]:
    await _get_book(session, user, book_id)
    result = await session.execute(
        select(ReviewJob).where(
            ReviewJob.book_id == book_id,
        ).order_by(ReviewJob.created_at.desc()),
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# versioned save
# ---------------------------------------------------------------------------
async def _save_versioned_chapter(
    session: AsyncSession,
    chapter: Chapter,
    new_content: str,
    *,
    version_type: str,
    metadata: dict[str, Any],
    user_id: UUID | None,
) -> None:
    chapter.content = new_content
    chapter.actual_word_count = len(re.findall(r"\S+", new_content or ""))
    chapter.is_approved = False

    max_result = await session.execute(
        select(func.max(ChapterVersion.version_number)).where(
            ChapterVersion.chapter_id == chapter.id,
        ),
    )
    next_ver = (max_result.scalar() or 0) + 1
    version = ChapterVersion(
        chapter_id=chapter.id,
        version_number=next_ver,
        content=new_content,
        word_count=chapter.actual_word_count,
        version_type=version_type,
        generation_metadata=metadata,
        created_by=user_id,
    )
    session.add(version)


# ---------------------------------------------------------------------------
# location data helper
# ---------------------------------------------------------------------------
def _build_location(full_text: str, snippet: str) -> dict[str, Any]:
    if not snippet or not full_text:
        return {}
    idx = full_text.find(snippet)
    if idx >= 0:
        return {"start": idx, "end": idx + len(snippet), "anchor": snippet[:40]}
    return {"anchor": snippet[:40]}


# ---------------------------------------------------------------------------
# apply suggestion to chapter content
# ---------------------------------------------------------------------------
def _apply_suggestion(content: str, sug: EditingSuggestion) -> str:
    """Simple string replacement: find original_text and replace it with suggested_text.

    If original_text appears multiple times, replaces the first occurrence.
    If original_text can't be found, appends suggested_text at the end."""
    if not sug.suggested_text:
        return content
    if not sug.original_text:
        return content
    if sug.suggested_text == sug.original_text:
        return content

    idx = content.find(sug.original_text)
    if idx >= 0:
        return content[:idx] + sug.suggested_text + content[idx + len(sug.original_text):]
    # Fallback: could not locate original — don't destroy content.
    return content


def _initial_progress_data(chapters: list[Chapter]) -> list[dict[str, Any]]:
    return [
        {"chapter_id": str(ch.id), "chapter_title": ch.title, "status": "queued"}
        for ch in chapters
    ]