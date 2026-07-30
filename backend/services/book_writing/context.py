"""Phase 6 — Context management for the book-writing engine.

The context system assembles the *relevant* book context for each AI request so
we never blindly send the entire book. Three builders are provided:

* :func:`build_book_context`        — brief + blueprint + style profile
* :func:`build_chapter_context`     — book context + current chapter outline/summary
* :func:`build_continuation_context`— chapter context + previous chapter summary + prior content

All builders are token-aware: long fields are truncated, and only approved
content / recent context is included. This keeps generation cheap and within
provider context windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from models.book_writing import (
    BookBlueprint,
    BookBrief,
    WritingBook as Book,
    WritingBookSettings as BookSettings,
    WritingChapter as Chapter,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Approximate safety caps to avoid blowing up context windows.
_MAX_SUMMARY_CHARS = 600
_MAX_CONTENT_CHARS = 6000
_MAX_PRIOR_CONTENT_CHARS = 2500


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


@dataclass
class StyleProfile:
    """Normalized writing-style profile passed to the engine."""

    tone: str | None = None
    formality: str | None = None
    sentence_complexity: str | None = None
    paragraph_length: str | None = None
    use_examples: str | None = None
    use_stories: str | None = None
    use_analogies: str | None = None
    use_humor: str | None = None
    use_practical_exercises: str | None = None
    point_of_view: str | None = None
    reading_level: str | None = None
    style_notes: str | None = None

    @classmethod
    def from_settings(cls, settings: BookSettings | None) -> StyleProfile:
        if settings is None:
            return cls()
        return cls(
            tone=settings.tone,
            formality=settings.formality,
            sentence_complexity=settings.sentence_complexity,
            paragraph_length=settings.paragraph_length,
            use_examples=settings.use_examples,
            use_stories=settings.use_stories,
            use_analogies=settings.use_analogies,
            use_humor=settings.use_humor,
            use_practical_exercises=settings.use_practical_exercises,
            point_of_view=settings.point_of_view,
            reading_level=settings.reading_level,
            style_notes=settings.style_notes,
        )

    def to_guidance(self) -> str:
        """Render the profile as a compact prose guidance string for prompts."""
        parts: list[str] = []
        if self.tone:
            parts.append(f"Tone: {self.tone}.")
        if self.formality:
            parts.append(f"Formality: {self.formality}.")
        if self.reading_level:
            parts.append(f"Reading level: {self.reading_level}.")
        if self.point_of_view:
            pov = {
                "first_person": "first person",
                "second_person": "second person (you)",
                "third_person": "third person",
            }.get(self.point_of_view, self.point_of_view)
            parts.append(f"Point of view: {pov}.")
        if self.sentence_complexity:
            parts.append(f"Sentence complexity: {self.sentence_complexity}.")
        if self.paragraph_length:
            parts.append(f"Paragraph length: {self.paragraph_length}.")
        flags = {
            "use_examples": self.use_examples,
            "use_stories": self.use_stories,
            "use_analogies": self.use_analogies,
            "use_humor": self.use_humor,
            "use_practical_exercises": self.use_practical_exercises,
        }
        for label, value in flags.items():
            if value and value != "low":
                parts.append(f"Use {label.replace('_', ' ')}: {value}.")
        if self.style_notes:
            parts.append(self.style_notes)
        return " ".join(parts) if parts else "Clear, accessible, professional prose."


@dataclass
class BookContext:
    """Lightweight, serializable book context bundle."""

    book: Book
    brief: BookBrief | None = None
    blueprint: BookBlueprint | None = None
    style: StyleProfile = field(default_factory=StyleProfile)

    # Rendered strings (already truncated) for prompt assembly.
    brief_summary: str = ""
    blueprint_summary: str = ""
    style_guidance: str = ""


def _render_brief(brief: BookBrief | None) -> str:
    if brief is None:
        return ""
    lines: list[str] = []
    if brief.working_title:
        lines.append(f"Working title: {brief.working_title}")
    if brief.book_purpose:
        lines.append(f"Purpose: {_truncate(brief.book_purpose, _MAX_SUMMARY_CHARS)}")
    if brief.target_reader:
        lines.append(f"Target reader: {_truncate(brief.target_reader, 200)}")
    if brief.reader_problems:
        lines.append("Reader problems: " + "; ".join(brief.reader_problems[:6]))
    if brief.promised_transformation:
        lines.append(f"Promised transformation: {_truncate(brief.promised_transformation, 200)}")
    if brief.tone:
        lines.append(f"Tone: {brief.tone}")
    if brief.writing_style:
        lines.append(f"Writing style: {brief.writing_style}")
    if brief.key_themes:
        lines.append("Key themes: " + "; ".join(brief.key_themes[:8]))
    if brief.major_concepts:
        lines.append("Major concepts: " + "; ".join(brief.major_concepts[:8]))
    if brief.topics_to_avoid:
        lines.append("Topics to avoid: " + "; ".join(brief.topics_to_avoid[:8]))
    if brief.suggested_structure:
        lines.append(f"Suggested structure: {_truncate(brief.suggested_structure, 300)}")
    return "\n".join(lines)


def _render_blueprint(book: Book, blueprint: BookBlueprint | None) -> str:
    if blueprint is None:
        return ""
    lines: list[str] = []
    if blueprint.introduction_purpose:
        lines.append(f"Introduction purpose: {_truncate(blueprint.introduction_purpose, 200)}")
    for idx, ch in enumerate(blueprint.chapters[:40], start=1):
        title = ch.get("title", f"Chapter {idx}")
        objective = _truncate(ch.get("objective"), 200)
        lines.append(f"{idx}. {title}" + (f" — {objective}" if objective else ""))
    return "\n".join(lines)


async def build_book_context(
    session: AsyncSession,
    book: Book,
    *,
    brief: BookBrief | None = None,
    blueprint: BookBlueprint | None = None,
    settings: BookSettings | None = None,
) -> BookContext:
    """Assemble book-level context (brief + blueprint + style)."""
    if brief is None:
        from sqlalchemy import select

        result = await session.execute(
            select(BookBrief).where(BookBrief.book_id == book.id, BookBrief.deleted_at.is_(None))
        )
        brief = result.scalar_one_or_none()
    if blueprint is None:
        from sqlalchemy import select

        result = await session.execute(
            select(BookBlueprint).where(
                BookBlueprint.book_id == book.id, BookBlueprint.deleted_at.is_(None)
            )
        )
        blueprint = result.scalar_one_or_none()
    if settings is None:
        from sqlalchemy import select

        result = await session.execute(
            select(BookSettings).where(
                BookSettings.book_id == book.id, BookSettings.deleted_at.is_(None)
            )
        )
        settings = result.scalar_one_or_none()

    style = StyleProfile.from_settings(settings)
    return BookContext(
        book=book,
        brief=brief,
        blueprint=blueprint,
        style=style,
        brief_summary=_render_brief(brief),
        blueprint_summary=_render_blueprint(book, blueprint),
        style_guidance=style.to_guidance(),
    )


async def build_chapter_context(
    session: AsyncSession,
    book: Book,
    chapter: Chapter,
    *,
    book_context: BookContext | None = None,
) -> dict[str, Any]:
    """Assemble context for generating/editing a single chapter.

    Includes the book context plus the chapter's own outline, objective, and
    summary (truncated), but not the full manuscript.
    """
    if book_context is None:
        book_context = await build_book_context(session, book)

    outline = chapter.outline or ""
    if not outline and chapter.outline_sections:
        outline = "\n".join(
            f"- {s.get('title', '')}: " + "; ".join(s.get("key_points", [])[:6])
            for s in chapter.outline_sections[:20]
        )

    return {
        "book_title": book.title,
        "book_subtitle": book.subtitle or "",
        "author_name": book.author_name or "",
        "target_audience": book.target_audience or "",
        "language": book.language,
        "brief_summary": book_context.brief_summary,
        "blueprint_summary": book_context.blueprint_summary,
        "style_guidance": book_context.style_guidance,
        "chapter_number": chapter.chapter_number,
        "chapter_title": chapter.title,
        "chapter_purpose": chapter.purpose or "",
        "chapter_objective": chapter.objective or "",
        "chapter_summary": _truncate(chapter.summary, _MAX_SUMMARY_CHARS),
        "chapter_outline": _truncate(outline, 1500),
        "target_word_count": chapter.target_word_count or 0,
    }


async def build_continuation_context(
    session: AsyncSession,
    book: Book,
    chapter: Chapter,
    *,
    book_context: BookContext | None = None,
    include_prior_content: bool = True,
) -> dict[str, Any]:
    """Assemble context for continuing a chapter that already has content.

    Includes the chapter context plus the *previous chapter's* summary and a
    tail of the *current* chapter's existing content so the model can continue
    seamlessly without re-sending the whole book.
    """
    from sqlalchemy import select

    chapter_ctx = await build_chapter_context(session, book, chapter, book_context=book_context)

    # Previous chapter summary (for transitions).
    prev_summary = ""
    prev_result = await session.execute(
        select(Chapter)
        .where(
            Chapter.book_id == book.id,
            Chapter.chapter_number == chapter.chapter_number - 1,
            Chapter.deleted_at.is_(None),
        )
        .order_by(Chapter.chapter_number)
    )
    prev_chapter = prev_result.scalars().first()
    if prev_chapter is not None:
        prev_summary = _truncate(prev_chapter.summary, 400) or _truncate(
            prev_chapter.content, 400
        )

    prior_content = ""
    if include_prior_content and chapter.content:
        prior_content = _truncate(chapter.content, _MAX_PRIOR_CONTENT_CHARS)

    chapter_ctx.update(
        {
            "previous_chapter_summary": prev_summary,
            "prior_content": prior_content,
        }
    )
    return chapter_ctx
