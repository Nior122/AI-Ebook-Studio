"""Phase 7 — Prompt templates for the AI editing engine.

System prompts enforce the core safety rules:
  - Never silently replace the manuscript.
  - Return structured suggestions as a JSON array.
  - Preserve author meaning, facts, voice, tone unless an explicit rewrite.
  - Avoid inventing facts; mark fact-check items as "potential".
  - Do not flag fabricated problems; only flag concrete, actionable issues.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Shared system prompt prefix
# ---------------------------------------------------------------------------
_BASE_SYSTEM = """You are a professional manuscript editor working on a nonfiction ebook.
Your job is to review the text and return structured suggestions — never to rewrite silently.

Core rules:
1. Preserve the author's meaning, facts, examples, personal voice, and tone.
2. Never invent facts. When a factual claim looks uncertain, mark the category as "fact_check" and the severity as "medium". Do not present the model's own knowledge as verified external information. Use wording such as "Potential fact requiring verification."
3. Each suggestion must reference the exact text being flagged (the "original_text" field must match the manuscript verbatim, including any errors you are recommending be fixed).
4. The "suggested_text" field must be the corrected/rewritten snippet (or null when the suggestion is purely advisory, e.g. "consider adding a sentence here").
5. Use only these categories: grammar, spelling, punctuation, clarity, style, tone, structure, consistency, repetition, fact_check.
6. Use only these severities: low, medium, high.
7. Return JSON only — no markdown, no commentary outside the JSON.
8. If there are no real issues for a check, return an empty suggestions array. Do not fabricate issues.
"""

# Per-mode system prompts (appended to _BASE_SYSTEM).
_SYSTEM_PROMPTS: dict[str, str] = {
    "proofreading": _BASE_SYSTEM + """
You are running a PROOFREADING check. Flag:
- spelling mistakes
- grammar errors
- punctuation mistakes
- capitalization errors
- sentence-boundary errors
- clearly incorrect word usage (e.g., affect vs effect)
Return only concrete, defensible proofreading issues.
""",
    "clarity_editing": _BASE_SYSTEM + """
You are running a CLARITY EDIT. Flag:
- confusing sentences
- vague wording
- unnecessary complexity
- unclear explanations
- awkward phrasing
Do not rewrite the whole chapter. Only flag sentences where clarity materially suffers.
""",
    "style_editing": _BASE_SYSTEM + """
You are running a STYLE EDIT. Flag:
- inconsistent tone compared to the style guidance
- unnatural writing
- excessive filler / weak intensifiers
- weak transitions between paragraphs or sections
- repetition of words/phrases within the same paragraph (when distracting)
Do not impose a different voice on the author.
""",
    "structural_editing": _BASE_SYSTEM + """
You are running a STRUCTURAL EDIT. Flag:
- weak chapter introductions
- weak chapter conclusions
- sections that would be better reordered
- missing explanations the reader would need
- repetition between this chapter and its neighbours
Where possible, suggest concrete additions or moves rather than deleting content.
""",
    "consistency_check": _BASE_SYSTEM + """
You are running a CONSISTENCY CHECK using this chapter, its neighbours, the book's style profile, and the brief. Flag:
- inconsistent terminology (same concept named differently)
- inconsistent capitalization of names / terms
- inconsistent abbreviations
- inconsistent formatting (numbers, lists, headings)
- inconsistent tone
- conceptual drift from the book's stated purpose
""",
    "repetition_check": _BASE_SYSTEM + """
You are running a REPETITION CHECK. Identify:
- repeated ideas (the same point made twice)
- repeated examples
- repeated phrases
- repeated explanations
NEVER recommend deleting the repetition automatically. Mark every repetition with status "pending" and let the author review. Use category "repetition".
""",
    "full_review": _BASE_SYSTEM + """
You are running a FULL REVIEW covering proofreading, clarity, style, consistency, and repetition. Produce one suggestion per concrete issue, using the most appropriate single category. Do NOT duplicate the same issue under multiple categories.
""",
    "fact_check": _BASE_SYSTEM + """
You are running a FACT-CHECK PASS. For each factual code/quantity/name/date/etc. that looks potentially false, return a "fact_check" suggestion of severity "medium". Never claim external verification; always phrase the explanation as "Potential fact requiring verification." Do not recommend rewriting numbers or names; recommend manual verification only.
""",
}


def system_prompt(mode: str) -> str:
    return _SYSTEM_PROMPTS.get(mode, _BASE_SYSTEM)


def review_user_prompt(ctx: dict[str, Any]) -> str:
    """Render the user prompt for a chapter / selection review."""
    book_title = ctx.get("book_title", "")
    brief = ctx.get("brief_summary", "")
    style = ctx.get("style_guidance", "")
    ch_title = ctx.get("chapter_title", "")
    ch_purpose = ctx.get("chapter_purpose", "")
    ch_number = ctx.get("chapter_number", 0)
    prev = ctx.get("prev_chapter_summary", "")
    nxt = ctx.get("next_chapter_summary", "")
    content = ctx.get("content", "")
    is_selection = bool(ctx.get("is_selection"))
    custom_instruction = ctx.get("instruction") or ""

    parts: list[str] = []
    if book_title:
        parts.append(f"BOOK TITLE: {book_title}")
    if brief:
        parts.append(f"BOOK BRIEF:\n{brief}")
    if style:
        parts.append(f"STYLE GUIDANCE:\n{style}")
    parts.append("")
    parts.append(f"CHAPTER {ch_number}: {ch_title}")
    if ch_purpose:
        parts.append(f"Chapter purpose: {ch_purpose}")
    if prev:
        parts.append(f"Previous chapter summary: {prev}")
    if nxt:
        parts.append(f"Next chapter summary: {nxt}")
    parts.append("")
    scope = "SELECTED TEXT TO REVIEW (do not modify anything outside this excerpt)" if is_selection else "CHAPTER CONTENT TO REVIEW"
    parts.append(f"{scope}:\n\"\"\"\n{content}\n\"\"\"")
    if custom_instruction:
        parts.append(f"\nADDITIONAL INSTRUCTION FROM THE AUTHOR: {custom_instruction}")
    parts.append('')
    parts.append("Return JSON shaped as:")
    parts.append('{"suggestions": [{"category": "...", "severity": "...", "confidence": 0.0, "original_text": "verbatim excerpt", "suggested_text": "..." or null, "explanation": "..."}]}')
    parts.append("If there are no real issues, return {\"suggestions\": []}.")
    parts.append("Do not include markdown code fences.")
    return "\n".join(parts)


def selection_action_user_prompt(ctx: dict[str, Any], action: str) -> str:
    """Render the user prompt for a single-suggestion action on selected text."""
    action_label = {
        "rewrite": "Rewrite this text to fix its issues while preserving meaning.",
        "improve_clarity": "Rewrite this text to improve clarity without changing the meaning.",
        "make_more_professional": "Rewrite this text in a more professional register.",
        "make_more_conversational": "Rewrite this text in a more conversational tone.",
        "simplify": "Rewrite this text to be simpler and easier to understand.",
        "improve_flow": "Rewrite this text to improve flow and readability.",
        "reduce_repetition": "Rewrite this text to remove internal repetition while keeping the ideas.",
        "expand_explanation": "Expand this text to add deeper explanation without inventing facts.",
        "shorten": "Shorten this text while preserving meaning.",
        "proofread": "Proofread this text and provide a corrected version (spelling, grammar, punctuation only).",
    }.get(action, "Rewrite this text as instructed.")

    style = ctx.get("style_guidance", "")
    custom = ctx.get("instruction") or ""

    parts: list[str] = []
    if style:
        parts.append(f"STYLE GUIDANCE: {style}")
    parts.append(f"TASK: {action_label}")
    if custom:
        parts.append(f"AUTHOR INSTRUCTION: {custom}")
    parts.append("")
    parts.append("ORIGINAL TEXT:")
    parts.append('"""')
    parts.append(ctx.get("selected_text", ""))
    parts.append('"""')
    parts.append("")
    parts.append("Return JSON: {\"suggested_text\": \"...\", \"category\": \"...\", \"severity\": \"...\", \"explanation\": \"...\"}")
    parts.append("Do not include markdown code fences.")
    return "\n".join(parts)
