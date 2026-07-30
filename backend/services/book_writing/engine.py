"""Phase 6 — AI Writing Engine.

The :class:`BookWritingEngine` is the only component that talks to the AI layer.
It uses :class:`AIService` (Phase 5) so it works with *any* configured provider
and model — no provider SDK is imported here.

Every public method follows the same pattern:

1. Build the relevant context via :mod:`services.book_writing.context`.
2. Render (system, user) prompts via :mod:`services.book_writing.prompts`.
3. Call ``ai_service.generate_structured_output`` (or ``generate_text``).
4. Normalize the result into plain strings / dicts for the service layer.

The engine never persists anything — persistence lives in ``service.py``.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from providers.ai.base import Message
from services.ai_service import AIService

from .context import (
    StyleProfile,
    build_book_context,
    build_chapter_context,
    build_continuation_context,
)
from .prompts import (
    _BLUEPRINT_SYSTEM,
    _BRIEF_SYSTEM,
    _CHAPTER_SYSTEM,
    _EDIT_SYSTEM,
    _OUTLINE_SYSTEM,
    blueprint_user_prompt,
    brief_user_prompt,
    chapter_content_user_prompt,
    chapter_outline_user_prompt,
    continue_chapter_user_prompt,
    edit_user_prompt,
    transition_user_prompt,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# JSON schemas for structured generation
# ---------------------------------------------------------------------------
_BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "working_title": {"type": "string"},
        "subtitle": {"type": "string"},
        "book_purpose": {"type": "string"},
        "target_reader": {"type": "string"},
        "reader_problems": {"type": "array", "items": {"type": "string"}},
        "promised_transformation": {"type": "string"},
        "tone": {"type": "string"},
        "writing_style": {"type": "string"},
        "key_themes": {"type": "array", "items": {"type": "string"}},
        "major_concepts": {"type": "array", "items": {"type": "string"}},
        "topics_to_avoid": {"type": "array", "items": {"type": "string"}},
        "suggested_structure": {"type": "string"},
        "estimated_chapter_count": {"type": "integer"},
        "estimated_word_count": {"type": "integer"},
    },
    "required": ["working_title", "book_purpose", "key_themes"],
}

_BLUEPRINT_SCHEMA = {
    "type": "object",
    "properties": {
        "introduction_purpose": {"type": "string"},
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "objective": {"type": "string"},
                    "summary": {"type": "string"},
                    "key_lessons": {"type": "array", "items": {"type": "string"}},
                    "important_examples": {"type": "array", "items": {"type": "string"}},
                    "practical_exercises": {"type": "array", "items": {"type": "string"}},
                    "estimated_word_count": {"type": "integer"},
                    "connects_to_previous": {"type": "string"},
                    "connects_to_future": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    "required": ["chapters"],
}

_OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "purpose": {"type": "string"},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title"],
            },
        },
    },
    "required": ["title", "sections"],
}

_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {"content": {"type": "string"}},
    "required": ["content"],
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class BookWritingEngine:
    """Provider-agnostic AI writing engine (outline / draft / edit)."""

    def __init__(self, ai_service: AIService) -> None:
        self.ai = ai_service

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    async def _structured(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        provider: str | None,
        model: str | None,
        temperature: float,
        task: str,
        book_id: Any | None = None,
        user_id: Any | None = None,
    ) -> dict[str, Any]:
        messages = [Message(role="system", content=system), Message(role="user", content=user)]
        return await self.ai.generate_structured_output(
            messages=messages,
            schema=schema,
            provider=provider,
            model=model,
            task=task,
            temperature=temperature,
            user_id=user_id,
            metadata={"feature": "book_writing", "book_id": str(book_id) if book_id else None},
        )

    async def _text(
        self,
        *,
        system: str,
        user: str,
        provider: str | None,
        model: str | None,
        temperature: float,
        task: str,
        book_id: Any | None = None,
        user_id: Any | None = None,
    ) -> str:
        messages = [Message(role="system", content=system), Message(role="user", content=user)]
        response = await self.ai.generate_text(
            messages=messages,
            provider=provider,
            model=model,
            task=task,
            temperature=temperature,
            user_id=user_id,
            metadata={"feature": "book_writing", "book_id": str(book_id) if book_id else None},
        )
        return response.content

    # ------------------------------------------------------------------
    # book-level generation
    # ------------------------------------------------------------------
    async def generate_brief(
        self,
        session: Any,
        book: Any,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        user_id: Any | None = None,
    ) -> dict[str, Any]:
        """Generate a Book Brief from book metadata."""
        book_dict = {
            "title": book.title,
            "subtitle": book.subtitle,
            "description": book.description,
            "author_name": book.author_name,
            "target_audience": book.target_audience,
            "book_type": book.book_type,
            "language": book.language,
            "tone": book.tone,
            "approximate_length": book.approximate_length,
        }
        return await self._structured(
            system=_BRIEF_SYSTEM,
            user=brief_user_prompt(book_dict),
            schema=_BRIEF_SCHEMA,
            provider=provider,
            model=model,
            temperature=temperature,
            task="generate_book_brief",
            book_id=book.id,
            user_id=user_id,
        )

    async def generate_blueprint(
        self,
        session: Any,
        book: Any,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        user_id: Any | None = None,
    ) -> dict[str, Any]:
        """Generate a full Book Blueprint from the book context."""
        ctx = await build_book_context(session, book)
        return await self._structured(
            system=_BLUEPRINT_SYSTEM,
            user=blueprint_user_prompt(ctx.__dict__),
            schema=_BLUEPRINT_SCHEMA,
            provider=provider,
            model=model,
            temperature=temperature,
            task="generate_book_blueprint",
            book_id=book.id,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # chapter generation
    # ------------------------------------------------------------------
    async def generate_chapter_outline(
        self,
        session: Any,
        book: Any,
        chapter: Any,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.6,
        user_id: Any | None = None,
    ) -> dict[str, Any]:
        """Generate a structured outline for a single chapter."""
        ctx = await build_chapter_context(session, book, chapter)
        return await self._structured(
            system=_OUTLINE_SYSTEM,
            user=chapter_outline_user_prompt(ctx),
            schema=_OUTLINE_SCHEMA,
            provider=provider,
            model=model,
            temperature=temperature,
            task="generate_chapter_outline",
            book_id=book.id,
            user_id=user_id,
        )

    async def generate_chapter_content(
        self,
        session: Any,
        book: Any,
        chapter: Any,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.8,
        user_id: Any | None = None,
    ) -> str:
        """Generate the full prose content for a chapter."""
        ctx = await build_chapter_context(session, book, chapter)
        result = await self._structured(
            system=_CHAPTER_SYSTEM,
            user=chapter_content_user_prompt(ctx),
            schema=_CONTENT_SCHEMA,
            provider=provider,
            model=model,
            temperature=temperature,
            task="generate_chapter_content",
            book_id=book.id,
            user_id=user_id,
        )
        return _extract_text(result)

    async def continue_chapter(
        self,
        session: Any,
        book: Any,
        chapter: Any,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.8,
        user_id: Any | None = None,
    ) -> str:
        """Continue an existing (partial) chapter."""
        ctx = await build_continuation_context(session, book, chapter)
        result = await self._structured(
            system=_CHAPTER_SYSTEM,
            user=continue_chapter_user_prompt(ctx),
            schema=_CONTENT_SCHEMA,
            provider=provider,
            model=model,
            temperature=temperature,
            task="continue_chapter",
            book_id=book.id,
            user_id=user_id,
        )
        return _extract_text(result)

    async def generate_transition(
        self,
        session: Any,
        book: Any,
        from_chapter: Any,
        to_chapter: Any,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        user_id: Any | None = None,
    ) -> str:
        """Generate a transition paragraph between two chapters."""
        ctx = await build_chapter_context(session, book, to_chapter)
        result = await self._structured(
            system=_CHAPTER_SYSTEM,
            user=transition_user_prompt(ctx, from_chapter.title, to_chapter.title),
            schema=_CONTENT_SCHEMA,
            provider=provider,
            model=model,
            temperature=temperature,
            task="generate_transition",
            book_id=book.id,
            user_id=user_id,
        )
        return _extract_text(result)

    # ------------------------------------------------------------------
    # editing actions
    # ------------------------------------------------------------------
    async def edit_text(
        self,
        session: Any,
        book: Any,
        chapter: Any | None,
        action: str,
        *,
        instruction: str | None = None,
        selected_text: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.5,
        user_id: Any | None = None,
    ) -> str:
        """Apply an editing action (rewrite, expand, shorten, tone, …)."""
        if chapter is not None:
            ctx = await build_chapter_context(session, book, chapter)
        else:
            ctx = (await build_book_context(session, book)).__dict__
            ctx["content"] = selected_text or ""
        result = await self._structured(
            system=_EDIT_SYSTEM,
            user=edit_user_prompt(action, ctx, instruction or "", selected_text or ""),
            schema=_CONTENT_SCHEMA,
            provider=provider,
            model=model,
            temperature=temperature,
            task=f"edit_{action}",
            book_id=book.id,
            user_id=user_id,
        )
        return _extract_text(result)


# ---------------------------------------------------------------------------
# utilities
# ---------------------------------------------------------------------------
def _extract_text(result: dict[str, Any]) -> str:
    """Pull the ``content`` field out of a structured-output result.

    Tolerates a few common shapes and strips stray markdown fences defensively.
    """
    if not isinstance(result, dict):
        return str(result)
    text = result.get("content")
    if text is None:
        # Some models return nested keys; fall back to the first string value.
        for value in result.values():
            if isinstance(value, str) and value.strip():
                text = value
                break
    if text is None:
        text = json.dumps(result, ensure_ascii=False)
    return _strip_fences(text or "")


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` fences if the model returned them anyway."""
    cleaned = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    return cleaned
