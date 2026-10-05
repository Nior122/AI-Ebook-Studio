"""Chapter Revision prompts — targeted fixes driven by validation feedback.

When a chapter fails validation, the revision prompt feeds the validator's
issues back to the model so it can fix the specific problems instead of
blindly regenerating.
"""

from __future__ import annotations

from typing import Any

from .book_specification import render_spec_block


REVISION_SYSTEM = (
    "You are an expert book author revising one chapter based on a quality "
    "audit. Fix the listed problems while keeping everything that already works. "
    "Stay strictly within the locked Book Specification. Respond ONLY with valid "
    "JSON matching the requested schema. No markdown fences, no commentary."
)


def chapter_revision_user_prompt(
    spec: dict[str, Any],
    chapter_plan: dict[str, Any],
    outline_sections: list[dict[str, Any]],
    content: str,
    validation: dict[str, Any],
    *,
    chapter_number: int,
    target_word_count: int,
    style_guidance: str = "",
) -> str:
    outline_lines = "\n".join(
        f"  {i + 1}. {s.get('title', '')}: " + "; ".join((s.get("key_points") or [])[:6])
        for i, s in enumerate(outline_sections)
    )
    issues = validation.get("issues") or []
    missing = validation.get("missing_sections") or []
    bounded = content if len(content) <= 20000 else content[:20000] + "\n[...truncated...]"

    return (
        f"Revise Chapter {chapter_number} to fix the audit findings.\n\n"
        f"{render_spec_block(spec)}\n\n"
        f"CHAPTER PLAN:\n"
        f"Title: {chapter_plan.get('title', '')}\n"
        f"Objective: {chapter_plan.get('objective', '')}\n"
        f"Target word count: {target_word_count:,}\n\n"
        f"CHAPTER OUTLINE:\n{outline_lines}\n\n"
        "AUDIT FINDINGS TO FIX:\n"
        + ("".join(f"- {issue}\n" for issue in issues) or "- Improve overall quality.\n")
        + (f"Missing sections that must be added: " + "; ".join(missing) + "\n" if missing else "")
        + f"Scores — relevance: {validation.get('relevance_score')}, "
        f"coverage: {validation.get('outline_coverage')}, "
        f"depth: {validation.get('depth_score')}, "
        f"continuity: {validation.get('continuity_score')}\n\n"
        f"CURRENT CHAPTER CONTENT:\n{bounded}\n\n"
        f"Style guidance: {style_guidance or 'Clear, accessible, professional prose.'}\n\n"
        "Return the COMPLETE revised chapter (not a diff) as JSON: {content: str}."
    )
