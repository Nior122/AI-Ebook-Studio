"""Chapter Validation prompts — relevance, coverage, depth, continuity scoring.

After a chapter is assembled from its sections, an independent validation
request scores it against the locked specification and its outline. The result
gates acceptance: below-threshold chapters go to auto-revision.
"""

from __future__ import annotations

from typing import Any

from .book_specification import render_spec_block


VALIDATION_SYSTEM = (
    "You are a strict, honest book quality auditor. You score a finished "
    "chapter against the locked Book Specification and its outline. You do NOT "
    "rewrite anything — you only evaluate and report. Be strict: generic, "
    "off-topic, or thin content must score low. Respond ONLY with valid JSON "
    "matching the requested schema. No markdown fences, no commentary."
)


def chapter_validation_user_prompt(
    spec: dict[str, Any],
    chapter_plan: dict[str, Any],
    outline_sections: list[dict[str, Any]],
    content: str,
    *,
    chapter_number: int,
    target_word_count: int,
    previous_chapter_summary: str = "",
) -> str:
    outline_lines = "\n".join(
        f"  {i + 1}. {s.get('title', '')}: " + "; ".join((s.get("key_points") or [])[:6])
        for i, s in enumerate(outline_sections)
    )
    # Keep the content bounded for the validator's context window.
    bounded = content if len(content) <= 24000 else content[:24000] + "\n[...truncated...]"

    return (
        f"Audit Chapter {chapter_number} of '{spec.get('book_title', '')}'.\n\n"
        f"{render_spec_block(spec)}\n\n"
        f"CHAPTER PLAN:\n"
        f"Title: {chapter_plan.get('title', '')}\n"
        f"Objective: {chapter_plan.get('objective', '')}\n"
        f"Target word count: {target_word_count:,}\n\n"
        f"CHAPTER OUTLINE:\n{outline_lines}\n\n"
        + (f"PREVIOUS CHAPTER SUMMARY:\n{previous_chapter_summary}\n\n" if previous_chapter_summary else "")
        + f"CHAPTER CONTENT:\n{bounded}\n\n"
        "Score the chapter 0-100 on each dimension:\n"
        "- relevance_score: how strictly the content stays on the book's topic "
        "(penalize generic filler and off-topic material).\n"
        "- outline_coverage: percentage of outline sections/key points actually covered.\n"
        "- depth_score: specificity and substance (examples, steps, detail) vs fluff.\n"
        "- continuity_score: logical flow and consistency with the previous chapter "
        "and within the chapter itself.\n\n"
        "Also list concrete issues and any outline sections that are missing.\n\n"
        "Return JSON: {relevance_score: int, outline_coverage: int, depth_score: int, "
        "continuity_score: int, word_count: int, issues: [str], missing_sections: [str], "
        "summary: str}."
    )
