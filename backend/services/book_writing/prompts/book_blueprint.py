"""Book Blueprint prompts — the chapter-by-chapter architecture plan.

The blueprint expands the locked specification into an ordered list of chapter
plans. It is generated once and drives chapter creation, outlines, and the
continuity context passed to every chapter.
"""

from __future__ import annotations

from typing import Any

from .book_specification import render_spec_block


BLUEPRINT_SYSTEM = (
    "You are an expert nonfiction book architect. Using the locked Book "
    "Specification, design a complete chapter-by-chapter blueprint. Every "
    "chapter must directly serve the book's topic and main promise — no filler, "
    "no off-topic chapters. Chapters must build on each other in a logical "
    "learning order. Respond ONLY with valid JSON matching the requested "
    "schema. No markdown fences, no commentary."
)


def blueprint_user_prompt(spec: dict[str, Any], style_guidance: str = "") -> str:
    chapter_count = int(spec.get("chapter_count") or 10)
    target_words = int(spec.get("target_word_count") or 10000)
    words_per = max(target_words // max(chapter_count, 1), 500)

    return (
        "Design the full chapter blueprint for this book.\n\n"
        f"{render_spec_block(spec)}\n\n"
        f"Style guidance: {style_guidance or 'Clear, accessible, professional prose.'}\n\n"
        f"Produce EXACTLY {chapter_count} chapters (plus an introduction and a "
        f"conclusion plan). Each chapter should target roughly {words_per:,} words.\n\n"
        "Requirements:\n"
        "- Every chapter must map to at least one key/required topic from the specification.\n"
        "- Cover ALL required_topics across the blueprint; never cover excluded_topics.\n"
        "- Order chapters so each one builds on the previous (foundations first, "
        "advanced/practical later).\n"
        "- The introduction hooks the reader and states the promise; the conclusion "
        "recaps the transformation and gives next steps.\n\n"
        "Return JSON: {introduction_purpose: str, conclusion_purpose: str, "
        "estimated_total_word_count: int, chapters: [ {title, objective, summary, "
        "key_lessons[], important_examples[], practical_exercises[], "
        "estimated_word_count (int), connects_to_previous, connects_to_future} ] }."
    )
