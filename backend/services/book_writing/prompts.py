"""Phase 6 — Prompt templates for the book-writing engine.

Centralized, provider-agnostic prompt builders. They consume the context
dictionaries produced by :mod:`services.book_writing.context` and return
``(system, user)`` message tuples ready for :class:`AIService`.

Structured-output tasks use JSON-schema-shaped instructions so the engine can
rely on :meth:`AIService.generate_structured_output` instead of fragile parsing.
"""

from __future__ import annotations

from typing import Any


_BRIEF_SYSTEM = (
    "You are an expert developmental book editor and publishing strategist. "
    "Analyze the author's book idea and produce a structured, honest book brief. "
    "Respond ONLY with valid JSON matching the requested schema. "
    "Do not include markdown fences or commentary outside the JSON."
)

_BLUEPRINT_SYSTEM = (
    "You are an expert nonfiction/fiction book architect. "
    "Produce a detailed, chapter-by-chapter blueprint that expands the book brief "
    "into concrete chapters. Respond ONLY with valid JSON matching the requested "
    "schema. No markdown fences, no extra commentary."
)

_OUTLINE_SYSTEM = (
    "You are a professional chapter outline writer. "
    "Produce a structured chapter outline as JSON matching the requested schema. "
    "No markdown fences, no extra commentary."
)

_CHAPTER_SYSTEM = (
    "You are an expert book author. Write publication-ready prose that is engaging, "
    "well-structured, and consistent with the provided book context and style "
    "guidance. Respond ONLY with valid JSON matching the requested schema."
)

_EDIT_SYSTEM = (
    "You are a precise professional editor. Follow the instruction exactly while "
    "preserving the author's meaning and voice. Respond ONLY with valid JSON "
    "matching the requested schema. No markdown fences, no extra commentary."
)


def brief_user_prompt(book: dict[str, Any]) -> str:
    return (
        "Analyze this book idea and create a structured Book Brief.\n\n"
        f"Title: {book.get('title', '')}\n"
        f"Subtitle: {book.get('subtitle', '')}\n"
        f"Description: {book.get('description', '')}\n"
        f"Author: {book.get('author_name', '')}\n"
        f"Target audience: {book.get('target_audience', '')}\n"
        f"Book type: {book.get('book_type', '')}\n"
        f"Language: {book.get('language', 'en')}\n"
        f"Tone: {book.get('tone', '')}\n"
        f"Approximate length: {book.get('approximate_length', '')}\n\n"
        "Return a JSON object with: working_title, subtitle, book_purpose, "
        "target_reader, reader_problems (array), promised_transformation, tone, "
        "writing_style, key_themes (array), major_concepts (array), "
        "topics_to_avoid (array), suggested_structure, estimated_chapter_count "
        "(int), estimated_word_count (int)."
    )


def blueprint_user_prompt(ctx: dict[str, Any]) -> str:
    return (
        "Create a detailed book blueprint from the following context.\n\n"
        f"Book title: {ctx.get('book_title', '')}\n"
        f"Author: {ctx.get('author_name', '')}\n"
        f"Target audience: {ctx.get('target_audience', '')}\n"
        f"Language: {ctx.get('language', 'en')}\n"
        f"Style guidance: {ctx.get('style_guidance', '')}\n\n"
        f"BOOK BRIEF:\n{ctx.get('brief_summary', '') or 'No brief provided.'}\n\n"
        f"SUGGESTED STRUCTURE:\n{ctx.get('blueprint_summary', '') or 'Use a logical flow.'}\n\n"
        "Return JSON: {introduction_purpose: str, "
        "chapters: [ {title, objective, summary, key_lessons[], important_examples[], "
        "practical_exercises[], estimated_word_count (int), connects_to_previous, "
        "connects_to_future} ] }."
    )


def chapter_outline_user_prompt(ctx: dict[str, Any]) -> str:
    return (
        "Write a detailed outline for this chapter.\n\n"
        f"Book: {ctx.get('book_title', '')}\n"
        f"Chapter {ctx.get('chapter_number', '')}: {ctx.get('chapter_title', '')}\n"
        f"Objective: {ctx.get('chapter_objective', '')}\n"
        f"Summary: {ctx.get('chapter_summary', '')}\n"
        f"Target word count: {ctx.get('target_word_count', 0)}\n"
        f"Style guidance: {ctx.get('style_guidance', '')}\n\n"
        f"BOOK BRIEF:\n{ctx.get('brief_summary', '')}\n\n"
        f"BOOK BLUEPRINT (structure):\n{ctx.get('blueprint_summary', '')}\n\n"
        "Return JSON: {title: str, sections: [ {title, purpose, key_points[]} ] }."
    )


def chapter_content_user_prompt(ctx: dict[str, Any]) -> str:
    return (
        "Write the full content for this chapter based on its outline.\n\n"
        f"Book: {ctx.get('book_title', '')}\n"
        f"Chapter {ctx.get('chapter_number', '')}: {ctx.get('chapter_title', '')}\n"
        f"Purpose: {ctx.get('chapter_purpose', '')}\n"
        f"Objective: {ctx.get('chapter_objective', '')}\n"
        f"Target word count: {ctx.get('target_word_count', 0)}\n"
        f"Style guidance: {ctx.get('style_guidance', '')}\n"
        f"Target audience: {ctx.get('target_audience', '')}\n\n"
        f"CHAPTER OUTLINE:\n{ctx.get('chapter_outline', '')}\n\n"
        "Write complete, publication-ready prose. Use clear headings that match the "
        "outline sections, include concrete examples where appropriate, and end with "
        "a short transition to the next chapter if suitable.\n\n"
        "Return JSON: {content: str}."
    )


def continue_chapter_user_prompt(ctx: dict[str, Any]) -> str:
    return (
        "Continue writing the chapter from where it currently ends.\n\n"
        f"Book: {ctx.get('book_title', '')}\n"
        f"Chapter {ctx.get('chapter_number', '')}: {ctx.get('chapter_title', '')}\n"
        f"Target word count: {ctx.get('target_word_count', 0)}\n"
        f"Style guidance: {ctx.get('style_guidance', '')}\n\n"
        f"PREVIOUS CHAPTER SUMMARY:\n{ctx.get('previous_chapter_summary', '') or 'None'}\n\n"
        f"EXISTING CONTENT (so far):\n{ctx.get('prior_content', '') or 'None yet.'}\n\n"
        "Write the next portion of the chapter to continue seamlessly. "
        "Return JSON: {content: str}."
    )


def transition_user_prompt(ctx: dict[str, Any], from_title: str, to_title: str) -> str:
    return (
        "Write a short transition paragraph connecting two chapters.\n\n"
        f"Book: {ctx.get('book_title', '')}\n"
        f"From chapter: {from_title}\n"
        f"To chapter: {to_title}\n"
        f"Style guidance: {ctx.get('style_guidance', '')}\n\n"
        "Return JSON: {content: str}."
    )


def edit_user_prompt(action: str, ctx: dict[str, Any], instruction: str, selected_text: str) -> str:
    target = selected_text or ctx.get("content", "")
    action_label = {
        "rewrite": "Rewrite the following text",
        "expand": "Expand the following text with more detail and examples",
        "shorten": "Shorten the following text while preserving key meaning",
        "simplify": "Simplify the following text for clarity",
        "make_professional": "Make the following text more professional",
        "make_conversational": "Make the following text more conversational",
        "change_tone": "Change the tone of the following text",
        "add_examples": "Add illustrative examples to the following text",
        "add_story": "Add a relevant short story or anecdote to the following text",
        "add_analogy": "Add a helpful analogy to the following text",
        "improve_transition": "Improve the transition / flow of the following text",
        "fix_grammar": "Fix any grammar, spelling, and punctuation in the following text",
        "explain_clearly": "Rewrite the following text to explain the idea more clearly",
    }.get(action, "Revise the following text")

    extra = f" Specific instruction: {instruction}" if instruction else ""
    return (
        f"{action_label}.{extra}\n\n"
        f"Style guidance: {ctx.get('style_guidance', '')}\n\n"
        f"TEXT:\n{target}\n\n"
        "Return JSON: {content: str} containing the revised text only."
    )
