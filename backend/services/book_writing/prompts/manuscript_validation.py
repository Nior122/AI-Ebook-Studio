"""Manuscript Validation prompts — book-level quality report.

After all chapters are written, a final audit produces the book-level quality
report: overall scores, per-chapter flags, and whether the book is ready for
formatting.
"""

from __future__ import annotations

from typing import Any

from .book_specification import render_spec_block


MANUSCRIPT_VALIDATION_SYSTEM = (
    "You are a strict developmental editor performing the final quality audit "
    "of a complete manuscript against its locked Book Specification. You only "
    "evaluate and report; you never rewrite. Be honest — flag weak chapters. "
    "Respond ONLY with valid JSON matching the requested schema."
)


def manuscript_validation_user_prompt(
    spec: dict[str, Any],
    chapter_summaries: list[dict[str, Any]],
    *,
    total_word_count: int,
    chapter_validations: list[dict[str, Any]] | None = None,
) -> str:
    lines = [
        "Perform the final book-level quality audit.\n",
        render_spec_block(spec),
        "",
        f"Total manuscript word count: {total_word_count:,} "
        f"(target: {int(spec.get('target_word_count') or 0):,})",
        "",
        "CHAPTER SUMMARIES:",
    ]
    for cs in chapter_summaries:
        lines.append(
            f"- Chapter {cs.get('chapter_number')}: {cs.get('title')} "
            f"({cs.get('word_count', 0):,} words) — {cs.get('summary', '')}"
        )
    if chapter_validations:
        lines += ["", "PER-CHAPTER AUDIT SCORES:"]
        for cv in chapter_validations:
            lines.append(
                f"- Chapter {cv.get('chapter_number')}: relevance {cv.get('relevance_score')}, "
                f"coverage {cv.get('outline_coverage')}, depth {cv.get('depth_score')}, "
                f"continuity {cv.get('continuity_score')}, passed={cv.get('passed')}"
            )
    lines += [
        "",
        "Evaluate the book as a whole: does it deliver the main promise, cover all "
        "required topics, avoid excluded topics, and hold together as a coherent "
        "progression? Score overall_quality 0-100 and state whether the book is "
        "ready_for_formatting.",
        "",
        "Return JSON: {overall_quality: int, promise_delivered: bool, "
        "required_topics_covered: bool, coherence_score: int, "
        "ready_for_formatting: bool, weak_chapters: [int], issues: [str], "
        "recommendations: [str], summary: str}.",
    ]
    return "\n".join(lines)
