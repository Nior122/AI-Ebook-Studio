"""Chapter Section prompts — the unit of prose generation.

Chapters are NEVER generated in one shot. Each section of the chapter outline
is written as its own request, with the locked specification, the chapter
plan, the outline, previously written sections of the same chapter, and the
previous chapter's summary all included for continuity.
"""

from __future__ import annotations

from typing import Any

from .book_specification import render_spec_block


SECTION_SYSTEM = (
    "You are an expert book author writing one section of one chapter. Write "
    "substantive, publication-ready prose that is specific, concrete, and "
    "engaging. Stay strictly on the section's topic and within the locked Book "
    "Specification. Do not repeat content from earlier sections. Do not write "
    "headings for other sections. Respond ONLY with valid JSON matching the "
    "requested schema."
)


def chapter_section_user_prompt(
    spec: dict[str, Any],
    chapter_plan: dict[str, Any],
    outline_sections: list[dict[str, Any]],
    section_index: int,
    *,
    chapter_number: int,
    total_chapters: int,
    section_word_target: int,
    previous_chapter_summary: str = "",
    written_sections: list[dict[str, Any]] | None = None,
    style_guidance: str = "",
) -> str:
    section = outline_sections[section_index] if section_index < len(outline_sections) else {}
    lines = [
        f"Write ONE section of Chapter {chapter_number} of {total_chapters}.\n",
        render_spec_block(spec),
        "",
        f"CHAPTER: {chapter_plan.get('title', f'Chapter {chapter_number}')}",
        f"Chapter objective: {chapter_plan.get('objective', '')}",
        "",
        "FULL CHAPTER OUTLINE (write ONLY the assigned section):",
    ]
    for i, s in enumerate(outline_sections):
        marker = "  <-- WRITE THIS SECTION NOW" if i == section_index else ""
        points = "; ".join((s.get("key_points") or [])[:6])
        lines.append(f"  {i + 1}. {s.get('title', '')}: {points}{marker}")

    lines += [
        "",
        f"ASSIGNED SECTION: {section.get('title', '')}",
        f"Section purpose: {section.get('purpose', '')}",
        f"Key points to cover: " + "; ".join(section.get("key_points", []) or []),
        f"Target length for this section: ~{section_word_target:,} words.",
    ]

    if previous_chapter_summary:
        lines += ["", f"PREVIOUS CHAPTER SUMMARY (for continuity):\n{previous_chapter_summary}"]

    if written_sections:
        lines += ["", "SECTIONS ALREADY WRITTEN IN THIS CHAPTER (do not repeat them):"]
        for ws in written_sections:
            tail = (ws.get("content_tail") or "")[-800:]
            lines.append(f"--- {ws.get('title', '')} (excerpt of ending) ---\n{tail}")

    lines += [
        "",
        f"Style guidance: {style_guidance or 'Clear, accessible, professional prose.'}",
        "",
        "Writing rules:",
        "- Start with the section heading exactly as given (markdown ## heading).",
        "- Write flowing prose under that heading; use subheadings (###) only if helpful.",
        "- Be specific and practical: real examples, concrete steps, named tools/ideas.",
        "- No filler, no generic platitudes, no meta commentary about the book.",
        "- Do NOT write a chapter conclusion unless this is the final section.",
        "",
        "Return JSON: {content: str}.",
    ]
    return "\n".join(lines)
