"""Regression tests for the deterministic provider's book-writing tasks."""

from __future__ import annotations

import pytest

from providers.ai.base import GenerationConfig, GenerationRequest, Message
from providers.ai.local_provider import LocalProvider
from services.book_writing.prompts.book_blueprint import blueprint_user_prompt
from services.book_writing.prompts.book_specification import specification_user_prompt
from services.book_writing.prompts.chapter_outline import chapter_outline_user_prompt
from services.book_writing.prompts.chapter_section import chapter_section_user_prompt
from services.book_writing.prompts.chapter_validation import chapter_validation_user_prompt

_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {"content": {"type": "string"}},
    "required": ["content"],
}


def _section_request() -> GenerationRequest:
    spec = {
        "book_title": "AI Tools for Teachers",
        "topic": "Practical AI tools for K-12 teachers",
        "target_audience": "K-12 teachers with no technical background",
        "language": "en",
        "main_promise": "Help teachers save preparation time with safe, practical AI workflows.",
        "key_topics": ["lesson planning", "differentiated materials", "assessment"],
        "required_topics": ["privacy basics"],
        "chapter_count": 3,
        "target_word_count": 3000,
        "writing_style": "practical, clear, encouraging",
    }
    plan = {
        "title": "Planning Lessons with AI",
        "objective": "Help teachers use AI to plan lessons while protecting student privacy.",
        "summary": "A practical start to lesson planning with generative AI.",
        "key_lessons": [
            "Set a learning objective",
            "Give AI grade and subject context",
            "Review for accuracy and privacy",
        ],
    }
    sections = [
        {
            "title": "Writing a useful lesson-planning prompt",
            "purpose": "Show a safe, repeatable prompt workflow.",
            "key_points": [
                "State the learning objective",
                "Include grade and subject",
                "Remove student identifiers",
            ],
        },
        {
            "title": "Reviewing and adapting the draft",
            "purpose": "Check the output before classroom use.",
            "key_points": ["Verify factual claims", "Adapt to learner needs"],
        },
        {
            "title": "Putting the workflow into practice",
            "purpose": "Apply the process to a lesson.",
            "key_points": ["Start with one lesson", "Keep a reusable prompt template"],
        },
    ]
    prompt = chapter_section_user_prompt(
        spec,
        plan,
        sections,
        0,
        chapter_number=1,
        total_chapters=3,
        section_word_target=250,
    )
    return GenerationRequest(
        messages=[
            Message(role="system", content="Write one assigned chapter section."),
            Message(role="user", content=prompt),
        ],
        model="local/general",
        provider="local",
        config=GenerationConfig(json_mode=True, response_schema=_CONTENT_SCHEMA),
        metadata={"task": "generate_chapter_section"},
    )


@pytest.mark.asyncio
async def test_local_provider_generates_only_the_assigned_chapter_section() -> None:
    """A one-section request must not produce a generic multi-section chapter."""
    request = _section_request()

    result = await LocalProvider().generate_structured_output(request, _CONTENT_SCHEMA)
    content = result["content"]
    words = len(content.split())

    assert content.startswith("## Writing a useful lesson-planning prompt")
    assert content.count("## ") == 1
    assert 200 <= words <= 300
    assert "lesson-planning" in content.lower()
    assert "learning objective" in content.lower()
    assert "student identifiers" in content.lower()
    assert "Foundations" not in content
    assert "The book" not in content


def _task_request(task: str, prompt: str, schema: dict) -> GenerationRequest:
    return GenerationRequest(
        messages=[
            Message(role="system", content="Return only the requested structured result."),
            Message(role="user", content=prompt),
        ],
        model="local/general",
        provider="local",
        config=GenerationConfig(json_mode=True, response_schema=schema),
        metadata={"task": task},
    )


@pytest.mark.asyncio
async def test_local_provider_preserves_specification_and_blueprint_constraints() -> None:
    setup = {
        "details": {
            "title": "AI Tools for Teachers",
            "subtitle": "A Practical Classroom Guide",
            "topic": (
                "Using AI for lesson planning, differentiated materials, assessment, "
                "and student support"
            ),
            "target_audience": "K-12 teachers",
            "tone": "encouraging",
            "writing_style": "practical",
            "language": "en",
            "book_purpose": "Help teachers use AI safely in everyday classroom preparation.",
        },
        "size": {"total_word_count": 3000, "chapters_override": 3},
        "ai": {"reading_level": "beginner", "generate_exercises": True},
        "special_instructions": {"instructions": "Protect student privacy."},
    }
    specification_schema = {
        "type": "object",
        "properties": {
            "book_title": {"type": "string"},
            "topic": {"type": "string"},
            "chapter_count": {"type": "integer"},
            "target_word_count": {"type": "integer"},
        },
    }
    provider = LocalProvider()
    spec = await provider.generate_structured_output(
        _task_request(
            "generate_book_specification",
            specification_user_prompt(setup),
            specification_schema,
        ),
        specification_schema,
    )

    assert spec["book_title"] == "AI Tools for Teachers"
    assert spec["chapter_count"] == 3
    assert spec["target_word_count"] == 3000
    assert "lesson planning" in " ".join(spec["key_topics"]).lower()
    assert "teachers" in spec["target_audience"].lower()

    blueprint_schema = {
        "type": "object",
        "properties": {
            "introduction_purpose": {"type": "string"},
            "conclusion_purpose": {"type": "string"},
            "estimated_total_word_count": {"type": "integer"},
            "chapters": {"type": "array"},
        },
    }
    blueprint = await provider.generate_structured_output(
        _task_request("generate_book_blueprint", blueprint_user_prompt(spec), blueprint_schema),
        blueprint_schema,
    )

    assert len(blueprint["chapters"]) == 3
    titles = " ".join(chapter["title"] for chapter in blueprint["chapters"]).lower()
    assert "lesson planning" in titles
    assert "introduction" not in titles
    assert "conclusion" not in titles


@pytest.mark.asyncio
async def test_local_provider_outlines_one_chapter_and_does_not_fake_validation() -> None:
    spec = {
        "book_title": "AI Tools for Teachers",
        "topic": "Practical AI tools for K-12 teachers",
        "target_audience": "K-12 teachers",
        "language": "en",
        "main_promise": "Help teachers plan useful lessons safely.",
        "key_topics": ["lesson planning", "privacy basics", "assessment"],
        "required_topics": ["privacy basics"],
        "chapter_count": 3,
        "target_word_count": 3000,
    }
    plan = {
        "title": "Lesson Planning with AI",
        "objective": "Help teachers plan a lesson and protect student privacy.",
        "summary": "Define objectives, draft activities, and review AI output.",
        "key_lessons": ["State the learning objective", "Review accuracy and privacy"],
        "important_examples": ["A teacher prepares one science lesson"],
    }
    outline_schema = {
        "type": "object",
        "properties": {"title": {"type": "string"}, "sections": {"type": "array"}},
    }
    outline = await LocalProvider().generate_structured_output(
        _task_request(
            "generate_chapter_outline",
            chapter_outline_user_prompt(
                spec,
                plan,
                chapter_number=1,
                total_chapters=3,
                target_word_count=880,
            ),
            outline_schema,
        ),
        outline_schema,
    )
    assert outline["title"] == plan["title"]
    assert 3 <= len(outline["sections"]) <= 7
    assert all(
        any(
            term in section["title"].lower()
            for term in ("lesson", "teacher", "privacy", "objective")
        )
        for section in outline["sections"]
    )

    validation_schema = {
        "type": "object",
        "properties": {
            "relevance_score": {"type": "integer"},
            "outline_coverage": {"type": "integer"},
            "depth_score": {"type": "integer"},
            "continuity_score": {"type": "integer"},
        },
    }
    validation = await LocalProvider().generate_structured_output(
        _task_request(
            "validate_chapter",
            chapter_validation_user_prompt(
                spec,
                plan,
                outline["sections"],
                "A draft about lesson planning and privacy.",
                chapter_number=1,
                target_word_count=880,
            ),
            validation_schema,
        ),
        validation_schema,
    )
    assert validation["relevance_score"] is None
    assert validation["outline_coverage"] is None
    assert "cannot reliably judge" in validation["issues"][0].lower()
