"""Phase 7 — AI Manuscript Editing Engine.

The :class:`EditingEngine` is the only component that talks to the AI layer.
It uses :class:`AIService` (Phase 5) so it works with any configured provider
and model — no provider SDK is imported here. The engine never persists
anything; it returns structured suggestion dicts and the service layer writes
them to the database.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from providers.ai.base import AIProviderError, Message
from services.ai_service import AIService

from .context import ReviewContext, build_review_context
from .prompts import review_user_prompt, selection_action_user_prompt, system_prompt

logger = structlog.get_logger(__name__)


# JSON schema for the structured suggestions array returned by a review.
_SUGGESTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "severity": {"type": "string"},
                    "confidence": {"type": "number"},
                    "original_text": {"type": "string"},
                    "suggested_text": {"type": ["string", "null"]},
                    "explanation": {"type": "string"},
                },
                "required": ["category", "original_text", "explanation"],
            },
        }
    },
    "required": ["suggestions"],
}

# JSON schema for a single selection action (returns one suggestion).
_SINGLE_SUGGESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "suggested_text": {"type": "string"},
        "category": {"type": "string"},
        "severity": {"type": "string"},
        "confidence": {"type": "number"},
        "explanation": {"type": "string"},
        "original_text": {"type": "string"},
    },
    "required": ["suggested_text", "category", "explanation"],
}

_VALID_CATEGORIES = {
    "grammar", "spelling", "punctuation", "clarity", "style",
    "tone", "structure", "consistency", "repetition", "fact_check",
}
_VALID_SEVERITIES = {"low", "medium", "high"}


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    return match.group(1).strip() if match else cleaned


def _normalise_suggestion(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce one AI-returned suggestion into a safe dict shape."""
    category = str(raw.get("category", "clarity")).strip().lower()
    if category not in _VALID_CATEGORIES:
        category = "clarity"
    severity = str(raw.get("severity", "low")).strip().lower()
    if severity not in _VALID_SEVERITIES:
        severity = "low"
    confidence = raw.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else 0.5
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    original_text = str(raw.get("original_text") or "").strip()
    suggested_text = raw.get("suggested_text")
    if suggested_text is not None:
        suggested_text = str(suggested_text).strip() or None
    explanation = str(raw.get("explanation") or "").strip() or None
    return {
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "original_text": original_text,
        "suggested_text": suggested_text,
        "explanation": explanation,
    }


def _coerce_suggestions(result: Any) -> list[dict[str, Any]]:
    """Best-effort flatten of various model output shapes to a list of suggestion dicts."""
    if not isinstance(result, dict):
        return []
    raw = result.get("suggestions")
    if isinstance(raw, list):
        return [_normalise_suggestion(r) for r in raw if isinstance(r, dict)]
    # Some models wrap a single suggestion as the top-level object.
    if "category" in result or "original_text" in result:
        return [_normalise_suggestion(result)]
    return []


class EditingEngine:
    """Provider-agnostic AI manuscript editing engine."""

    def __init__(self, ai_service: AIService) -> None:
        self.ai = ai_service

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
        chapter_id: Any | None = None,
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
            metadata={
                "feature": "editing",
                "book_id": str(book_id) if book_id else None,
                "chapter_id": str(chapter_id) if chapter_id else None,
            },
        )

    # ------------------------------------------------------------------
    # Chapter / selection review
    # ------------------------------------------------------------------
    async def review_text(
        self,
        session: Any,
        book: Any,
        chapter: Any,
        *,
        mode: str = "proofreading",
        selected_text: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        user_id: Any | None = None,
        instruction: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a review (grammar/clarity/style/...) on a chapter or selection."""
        ctx: ReviewContext = await build_review_context(
            session, book, chapter, selected_text=selected_text,
        )
        ctx.extra["instruction"] = instruction
        system = system_prompt(mode)
        user = review_user_prompt(ctx.as_prompt_dict())
        result = await self._structured(
            system=system, user=user, schema=_SUGGESTIONS_SCHEMA,
            provider=provider, model=model, temperature=temperature,
            task=f"edit_review_{mode}",
            book_id=book.id, chapter_id=chapter.id, user_id=user_id,
        )
        return _coerce_suggestions(result)

    # ------------------------------------------------------------------
    # Single-suggestion selection action
    # ------------------------------------------------------------------
    async def act_on_selection(
        self,
        session: Any,
        book: Any,
        chapter: Any,
        *,
        action: str,
        selected_text: str,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.4,
        user_id: Any | None = None,
        instruction: str | None = None,
    ) -> dict[str, Any]:
        """Rewrite/improve/proofread a selected snippet → returns one suggestion dict."""
        ctx: ReviewContext = await build_review_context(
            session, book, chapter, selected_text=selected_text, include_neighbours=False,
        )
        ctx.extra["instruction"] = instruction
        system = system_prompt("proofreading")
        user = selection_action_user_prompt(ctx.as_prompt_dict(), action)
        result = await self._structured(
            system=system, user=user, schema=_SINGLE_SUGGESTION_SCHEMA,
            provider=provider, model=model, temperature=temperature,
            task=f"edit_action_{action}",
            book_id=book.id, chapter_id=chapter.id, user_id=user_id,
        )
        if not isinstance(result, dict):
            raise AIProviderError("AI returned a malformed response")
        suggestion = _normalise_suggestion({
            "category": result.get("category", "clarity"),
            "severity": result.get("severity", "low"),
            "confidence": result.get("confidence", result.get("confidence_score", 0.6)),
            "original_text": result.get("original_text", selected_text),
            "suggested_text": result.get("suggested_text"),
            "explanation": result.get("explanation"),
        })
        if not suggestion["suggested_text"]:
            # If we didn't get a usable suggested_text, use selected_text as-is
            # so we never destroy the user's content.
            suggestion["suggested_text"] = selected_text
        return suggestion
