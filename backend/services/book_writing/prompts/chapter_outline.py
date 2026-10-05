"""Chapter Outline prompts — section-level plan for a single chapter.

Each chapter gets a detailed outline of 3-7 sections before any prose is
written. Sections are the unit of generation: the pipeline writes the chapter
one section at a time.
"""

from __future__ import annotations

from typing import Any

from .book_specification import render_spec_block


OUTLINE_SYSTEM = (
    "You are a professional book outline writer. Produce a detailed, "
    "section-by-section outline for ONE chapter that stays strictly within the "
    "locked Book Specification. Respond ONLY with valid JSON matching the "
    "requested schema. No markdown fences, no commentary."
)


def chapter_outline_user_prompt(
    spec: dict[str, Any],
    chapter_plan: dict[str, Any],
    *,
    chapter_number: int,
    total_chapters: int,
    target_word_count: int,
    blueprint_titles: list[str] | None = None,
    style_guidance: str = "",
) -> str:
    lines = [
        f"Write the detailed outline for Chapter {chapter_number} of {total_chapters}.\n",
        render_spec_block(spec),
        "",
        f"CHAPTER PLAN:\n"
        f"Title: {chapter_plan.get('title', f'Chapter {chapter_number}')}\n"
        f"Objective: {chapter_plan.get('objective', '')}\n"
        f"Summary: {chapter_plan.get('summary', '')}\n"
        f"Key lessons: " + "; ".join(chapter_plan.get("key_lessons", []) or []),
    ]
    if chapter_plan.get("important_examples"):
        lines.append("Planned examples: " + "; ".join(chapter_plan["important_examples"]))
    if chapter_plan.get("practical_exercises"):
        lines.append("Planned exercises: " + "; ".join(chapter_plan["practical_exercises"]))
    if blueprint_titles:
        lines.append("\nAll chapter titles in this book (for scope awareness):")
        for i, t in enumerate(blueprint_titles, start=1):
            marker = "  <-- THIS CHAPTER" if i == chapter_number else ""
            lines.append(f"  {i}. {t}{marker}")
    lines += [
        "",
        f"Target word count for this chapter: {target_word_count:,}",
        f"Style guidance: {style_guidance or 'Clear, accessible, professional prose.'}",
        "",
        "Produce 3-7 sections (scale with the target word count: ~1 section per "
        "300-500 words). Every section must serve the chapter objective and stay "
        "on-topic per the specification. Include an opening hook section and a "
        "closing/transition section.",
        "",
        "Return JSON: {title: str, sections: [ {title, purpose, key_points[]} ] }.",
    ]
    return "\n".join(lines)
