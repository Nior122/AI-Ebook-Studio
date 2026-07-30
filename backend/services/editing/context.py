"""Phase 7 — Context for the AI editing engine.

Assembles the manuscript context the editor needs without sending the whole
book. Reuses Phase 6 builders (:mod:`services.book_writing.context`) for the
book-level context, and adds chapter-specific context plus neighbouring
chapter summaries that consistency checks need.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from models.book_writing import (
    WritingBook as Book,
    WritingChapter as Chapter,
)
from services.book_writing.context import build_chapter_context

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


_MAX_CONTENT_CHARS = 8000
_MAX_NEIGHBOUR_SUMMARY = 400


@dataclass
class ReviewContext:
    """Everything the editing engine needs for one chapter review."""

    book_title: str = ""
    brief_summary: str = ""
    style_guidance: str = ""
    chapter_title: str = ""
    chapter_purpose: str = ""
    chapter_number: int = 0
    content: str = ""
    selected_text: str | None = None
    prev_chapter_summary: str = ""
    next_chapter_summary: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def as_prompt_dict(self) -> dict[str, Any]:
        return {
            "book_title": self.book_title,
            "brief_summary": self.brief_summary,
            "style_guidance": self.style_guidance,
            "chapter_title": self.chapter_title,
            "chapter_purpose": self.chapter_purpose,
            "chapter_number": self.chapter_number,
            "content": self.selected_text or self.content,
            "is_selection": bool(self.selected_text),
            "prev_chapter_summary": self.prev_chapter_summary,
            "next_chapter_summary": self.next_chapter_summary,
            **self.extra,
        }


async def build_review_context(
    session: AsyncSession,
    book: Book,
    chapter: Chapter,
    *,
    selected_text: str | None = None,
    include_neighbours: bool = True,
) -> ReviewContext:
    """Build a :class:`ReviewContext` for one chapter review.

    Uses Phase 6 ``build_chapter_context`` (returns a dict) for the book-level
    context, then adds neighboring-chapter summaries when available.
    """
    from sqlalchemy import select

    ctx_dict = await build_chapter_context(session, book, chapter)

    prev_summary = ""
    next_summary = ""
    if include_neighbours and chapter.chapter_number is not None:
        prev_result = await session.execute(
            select(Chapter)
            .where(
                Chapter.book_id == book.id,
                Chapter.chapter_number == chapter.chapter_number - 1,
                Chapter.deleted_at.is_(None),
            )
        )
        prev_ch = prev_result.scalar_one_or_none()
        if prev_ch is not None and prev_ch.summary:
            prev_summary = prev_ch.summary[:_MAX_NEIGHBOUR_SUMMARY]

        next_result = await session.execute(
            select(Chapter)
            .where(
                Chapter.book_id == book.id,
                Chapter.chapter_number == chapter.chapter_number + 1,
                Chapter.deleted_at.is_(None),
            )
        )
        next_ch = next_result.scalar_one_or_none()
        if next_ch is not None and next_ch.summary:
            next_summary = next_ch.summary[:_MAX_NEIGHBOUR_SUMMARY]

    content = chapter.content or ""
    if len(content) > _MAX_CONTENT_CHARS:
        content = content[:_MAX_CONTENT_CHARS]

    return ReviewContext(
        book_title=ctx_dict.get("book_title", book.title),
        brief_summary=ctx_dict.get("brief_summary", ""),
        style_guidance=ctx_dict.get("style_guidance", ""),
        chapter_title=ctx_dict.get("chapter_title", chapter.title),
        chapter_purpose=ctx_dict.get("chapter_purpose", chapter.purpose or ""),
        chapter_number=ctx_dict.get("chapter_number", chapter.chapter_number or 0),
        content=content,
        selected_text=selected_text,
        prev_chapter_summary=prev_summary,
        next_chapter_summary=next_summary,
    )