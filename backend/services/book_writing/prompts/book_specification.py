"""Book Specification prompts — the TOPIC LOCK of the generation pipeline.

The specification is the single canonical definition of what the book is
about. It is produced once (from the user's setup payload) and then embedded
verbatim into every subsequent prompt — blueprint, outlines, sections,
validation, revision — so the model can never drift off-topic.

``render_spec_block`` is the shared renderer imported by every other prompt
module in this package.
"""

from __future__ import annotations

from typing import Any


SPEC_SYSTEM = (
    "You are an expert book development editor. Your job is to turn a raw book "
    "idea into a precise, locked Book Specification: the canonical definition "
    "of what this book is, who it is for, what it promises, and — critically — "
    "what it must cover and what it must NOT cover. Be concrete and specific; "
    "never generic. Respond ONLY with valid JSON matching the requested schema. "
    "No markdown fences, no commentary outside the JSON."
)


def render_spec_block(spec: dict[str, Any]) -> str:
    """Render the locked specification as a block embedded in every prompt."""
    lines = [
        "=== BOOK SPECIFICATION (LOCKED — DO NOT DEVIATE) ===",
        f"Title: {spec.get('book_title', '')}",
    ]
    if spec.get("subtitle"):
        lines.append(f"Subtitle: {spec['subtitle']}")
    lines.append(f"Topic: {spec.get('topic', '')}")
    if spec.get("description"):
        lines.append(f"Description: {spec['description']}")
    if spec.get("target_audience"):
        lines.append(f"Target audience: {spec['target_audience']}")
    if spec.get("book_type"):
        lines.append(f"Book type: {spec['book_type']}")
    lines.append(f"Language: {spec.get('language', 'en')}")
    if spec.get("tone"):
        lines.append(f"Tone: {spec['tone']}")
    if spec.get("main_promise"):
        lines.append(f"Main promise to the reader: {spec['main_promise']}")
    if spec.get("reader_problem"):
        lines.append(f"Reader's core problem: {spec['reader_problem']}")
    if spec.get("reader_transformation"):
        lines.append(f"Reader transformation: {spec['reader_transformation']}")
    if spec.get("key_topics"):
        lines.append("Key topics: " + "; ".join(spec["key_topics"]))
    if spec.get("required_topics"):
        lines.append("REQUIRED topics (must be covered): " + "; ".join(spec["required_topics"]))
    if spec.get("excluded_topics"):
        lines.append("EXCLUDED topics (never cover): " + "; ".join(spec["excluded_topics"]))
    lines.append(f"Planned chapters: {spec.get('chapter_count', 0)}")
    lines.append(f"Target word count: {spec.get('target_word_count', 0):,}")
    if spec.get("writing_style"):
        lines.append(f"Writing style: {spec['writing_style']}")
    if spec.get("difficulty_level"):
        lines.append(f"Difficulty level: {spec['difficulty_level']}")
    if spec.get("practical_focus"):
        lines.append("Practical focus: yes — include actionable, concrete guidance.")
    if spec.get("special_instructions"):
        lines.append(f"Author's special instructions: {spec['special_instructions']}")
    lines.append("=== END BOOK SPECIFICATION ===")
    return "\n".join(lines)


def specification_user_prompt(setup: dict[str, Any]) -> str:
    """Build the prompt that produces the specification from the setup payload."""
    details = setup.get("details", {}) or {}
    size = setup.get("size", {}) or {}
    ai = setup.get("ai", {}) or {}
    special = (setup.get("special_instructions", {}) or {}).get("instructions", "")

    return (
        "Turn this book idea into a locked Book Specification.\n\n"
        f"Title: {details.get('title', '')}\n"
        f"Subtitle: {details.get('subtitle', '') or ''}\n"
        f"Topic: {details.get('topic', '')}\n"
        f"Target audience: {details.get('target_audience', '')}\n"
        f"Tone: {details.get('tone', '')}\n"
        f"Writing style: {details.get('writing_style', '')}\n"
        f"Language: {details.get('language', 'en')}\n"
        f"Author: {details.get('author', '') or ''}\n"
        f"Book purpose: {details.get('book_purpose', '') or ''}\n"
        f"Requested total word count: {size.get('total_word_count', 0):,}\n"
        f"Requested chapter count: {size.get('chapters_override', '') or 'decide based on length'}\n"
        f"Reading level: {ai.get('reading_level', '') or 'general'}\n"
        f"Generate practical exercises: {ai.get('generate_exercises', False)}\n"
        f"Special instructions: {special or 'none'}\n\n"
        "Rules:\n"
        "- key_topics: 5-10 specific subtopics this book must cover.\n"
        "- required_topics: the 3-6 most essential topics the book absolutely must deliver on.\n"
        "- excluded_topics: adjacent topics that are OUT of scope (prevent drift).\n"
        "- main_promise: one sentence the book must deliver on by the end.\n"
        "- chapter_count: choose 6-8 for short books (<=10k words), 8-12 for medium "
        "(10k-25k), 12-20 for comprehensive (>25k). Respect the user's override if given.\n"
        "- difficulty_level: beginner | intermediate | advanced | mixed.\n\n"
        "Return JSON with: book_title, subtitle, topic, description, target_audience, "
        "book_type, language, tone, main_promise, reader_problem, reader_transformation, "
        "key_topics[], required_topics[], excluded_topics[], chapter_count (int), "
        "target_word_count (int), writing_style, difficulty_level, practical_focus (bool)."
    )
