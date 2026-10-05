"""Prompt templates for the book-writing engine.

This package holds every prompt used by the generation pipeline:

* ``legacy``               — original brief/blueprint/chapter/edit prompts
                             (still used by the interactive editor endpoints).
* ``book_specification``   — the TOPIC LOCK: canonical book definition, plus
                             ``render_spec_block`` embedded in every prompt.
* ``book_blueprint``       — chapter-by-chapter architecture plan.
* ``chapter_outline``      — section-level plan for one chapter.
* ``chapter_section``      — prose generation for ONE section (the unit of
                             generation; chapters are never one-shot).
* ``chapter_validation``   — relevance/coverage/depth/continuity audit.
* ``chapter_revision``     — targeted fixes driven by audit findings.
* ``introduction``         — introduction + conclusion, written last from the
                             real chapter summaries.
* ``manuscript_validation``— book-level quality report.

Legacy names are re-exported so existing imports keep working.
"""

from __future__ import annotations

from .legacy import (
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

__all__ = [
    "_BLUEPRINT_SYSTEM",
    "_BRIEF_SYSTEM",
    "_CHAPTER_SYSTEM",
    "_EDIT_SYSTEM",
    "_OUTLINE_SYSTEM",
    "blueprint_user_prompt",
    "brief_user_prompt",
    "chapter_content_user_prompt",
    "chapter_outline_user_prompt",
    "continue_chapter_user_prompt",
    "edit_user_prompt",
    "transition_user_prompt",
]
