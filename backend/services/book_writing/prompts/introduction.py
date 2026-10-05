"""Introduction prompts — generated AFTER all chapters, from real summaries.

Writing the introduction last (from actual chapter summaries) guarantees it
matches what the book really contains instead of a guess made up front.
"""

from __future__ import annotations

from typing import Any

from .book_specification import render_spec_block


INTRODUCTION_SYSTEM = (
    "You are an expert book author writing the Introduction of a finished book. "
    "Hook the reader, state the promise, and preview what each chapter delivers. "
    "Stay strictly within the locked Book Specification. Respond ONLY with valid "
    "JSON matching the requested schema."
)


def introduction_user_prompt(
    spec: dict[str, Any],
    chapter_summaries: list[dict[str, Any]],
    *,
    introduction_purpose: str = "",
    target_word_count: int = 800,
    style_guidance: str = "",
) -> str:
    lines = [
        "Write the Introduction for this book.\n",
        render_spec_block(spec),
        "",
        f"Introduction purpose from the blueprint: {introduction_purpose or 'Hook the reader and state the promise.'}",
        f"Target length: ~{target_word_count:,} words.",
        "",
        "THE FINISHED CHAPTERS (introduce what the reader will actually find):",
    ]
    for cs in chapter_summaries:
        lines.append(f"- Chapter {cs.get('chapter_number')}: {cs.get('title')} — {cs.get('summary', '')}")
    lines += [
        "",
        f"Style guidance: {style_guidance or 'Clear, accessible, professional prose.'}",
        "",
        "Requirements: open with a hook, name the reader's problem, state the "
        "transformation, then a brief chapter-by-chapter preview. Start with the "
        "heading '## Introduction'. Return JSON: {content: str}.",
    ]
    return "\n".join(lines)


CONCLUSION_SYSTEM = (
    "You are an expert book author writing the Conclusion of a finished book. "
    "Recap the transformation, tie the threads together, and give concrete next "
    "steps. Stay strictly within the locked Book Specification. Respond ONLY "
    "with valid JSON matching the requested schema."
)


def conclusion_user_prompt(
    spec: dict[str, Any],
    chapter_summaries: list[dict[str, Any]],
    *,
    conclusion_purpose: str = "",
    target_word_count: int = 700,
    style_guidance: str = "",
) -> str:
    lines = [
        "Write the Conclusion for this book.\n",
        render_spec_block(spec),
        "",
        f"Conclusion purpose from the blueprint: {conclusion_purpose or 'Recap the transformation and give next steps.'}",
        f"Target length: ~{target_word_count:,} words.",
        "",
        "THE FINISHED CHAPTERS (recap what the reader learned):",
    ]
    for cs in chapter_summaries:
        lines.append(f"- Chapter {cs.get('chapter_number')}: {cs.get('title')} — {cs.get('summary', '')}")
    lines += [
        "",
        f"Style guidance: {style_guidance or 'Clear, accessible, professional prose.'}",
        "",
        "Requirements: recap the journey and the delivered promise, reinforce the "
        "key takeaways, and end with concrete next steps or a call to action. Start "
        "with the heading '## Conclusion'. Return JSON: {content: str}.",
    ]
    return "\n".join(lines)
