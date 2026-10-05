"""Phase 6 repair — GenerationPipeline stage tests.

Drives the full multi-stage generation pipeline against an in-memory database
using a deterministic fake engine, so no external AI provider is contacted.

Covers: specification topic-lock, blueprint, per-chapter outlines,
section-by-section writing, validation gating, auto-revision, the
validation-unavailable fallback, introduction/conclusion, manuscript assembly
with quality report, resume (skip completed stages), and single-chapter
regeneration.
"""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select

from models.accounts import User
from models.book_writing import (
    ChapterVersion,
    Manuscript,
    WritingBook,
    WritingChapter,
)
from services.generation.pipeline import (
    GenerationPipeline,
    _audit_passed,
    _clamp_score,
    _normalize_validation,
    is_conclusion_title,
    regenerate_chapter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_FILLER = (
    "Teachers can use this practical strategy to improve classroom results "
    "while saving preparation time during a busy school week."
)  # 17 words


def _text(n_words: int) -> str:
    repeats = max(1, math.ceil(n_words / len(_FILLER.split())))
    return " ".join([_FILLER] * repeats)


class ProgressRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str | None]] = []

    async def __call__(self, pct: int, message: str | None = None) -> None:
        self.calls.append((pct, message))


class AnnounceRecorder:
    def __init__(self) -> None:
        self.kinds: list[str] = []

    async def __call__(self, kind: str, message: str) -> None:
        self.kinds.append(kind)


class FakeEngine:
    """Deterministic stand-in for BookWritingEngine's pipeline-facing methods.

    validation_mode controls the validate_chapter behaviour:
      - "pass": always high scores.
      - "fail_then_pass": first audit per chapter fails relevance, then passes.
      - "unavailable": unparseable scores (provider quirk) every time.
    """

    def __init__(self, validation_mode: str = "pass") -> None:
        self.validation_mode = validation_mode
        self.calls: dict[str, int] = {}
        self.section_specs: list[dict[str, Any]] = []  # first arg of each section call
        self.validate_results: list[dict[str, Any]] = []
        self.revise_calls = 0
        self._validate_attempts: dict[int, int] = {}

    def _count(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1

    async def generate_specification(self, setup: dict[str, Any], **_: Any) -> dict[str, Any]:
        self._count("generate_specification")
        details = setup.get("details", {}) or {}
        return {
            "book_title": "AI Tools for Teachers",
            "subtitle": "A Practical Classroom Guide",
            "topic": "Practical AI tools for K-12 teachers",
            "description": "How busy teachers can adopt AI tools.",
            "target_audience": "K-12 teachers with no technical background",
            "book_type": "practical guide",
            "language": "en",
            "tone": "encouraging and practical",
            "main_promise": "Save 5 hours a week with AI",
            "reader_problem": "Drowning in admin and grading work",
            "reader_transformation": "From overwhelmed to in control of their workload",
            "key_topics": ["lesson planning", "grading", "feedback"],
            "required_topics": ["privacy basics"],
            "excluded_topics": ["cryptocurrency"],
            "chapter_count": 8,
            "target_word_count": 3000,
            "writing_style": "conversational nonfiction",
            "difficulty_level": "beginner",
            "practical_focus": True,
        }

    async def generate_blueprint_from_spec(
        self, spec: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        self._count("generate_blueprint_from_spec")
        count = int(spec.get("chapter_count") or 3)
        return {
            "introduction_purpose": "Show the reader what is possible.",
            "conclusion_purpose": "Commit the reader to a 30-day plan.",
            "estimated_total_word_count": spec.get("target_word_count"),
            "chapters": [
                {
                    "title": f"Chapter {i + 1}: Getting Started with AI",
                    "objective": f"Achieve outcome {i + 1}",
                    "summary": f"Chapter {i + 1} teaches practical classroom AI usage.",
                    "estimated_word_count": 500,
                    "key_lessons": [f"Lesson {i + 1}.1", f"Lesson {i + 1}.2"],
                    "practical_exercises": [f"Exercise {i + 1}"],
                }
                for i in range(count)
            ],
        }

    async def generate_chapter_outline_from_spec(
        self, spec: dict[str, Any], plan: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        self._count("generate_chapter_outline_from_spec")
        return {
            "sections": [
                {"title": "Why this matters", "purpose": "Frame the problem.", "key_points": ["context"]},
                {"title": "The core method", "purpose": "Teach the method.", "key_points": ["steps"]},
                {"title": "Classroom application", "purpose": "Apply it.", "key_points": ["example"]},
            ]
        }

    async def generate_chapter_section(
        self,
        spec: dict[str, Any],
        plan: dict[str, Any],
        sections: list[dict[str, Any]],
        index: int,
        **_: Any,
    ) -> str:
        self._count("generate_chapter_section")
        self.section_specs.append(dict(spec))
        title = sections[index].get("title", "") if index < len(sections) else ""
        return f"## {title}\n\n{_text(136)}"

    async def validate_chapter(
        self,
        spec: dict[str, Any],
        plan: dict[str, Any],
        sections: list[dict[str, Any]],
        content: str,
        chapter_number: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        self._count("validate_chapter")
        attempt = self._validate_attempts.get(chapter_number, 0)
        self._validate_attempts[chapter_number] = attempt + 1
        result: dict[str, Any] = {
            "relevance_score": 92,
            "outline_coverage": 88,
            "depth_score": 80,
            "continuity_score": 85,
            "summary": f"Chapter {chapter_number} covers its outline fully.",
            "issues": [],
            "missing_sections": [],
        }
        if self.validation_mode == "fail_then_pass" and attempt == 0:
            result.update({"relevance_score": 35, "issues": ["Off-topic filler detected."]})
        if self.validation_mode == "unavailable":
            result.update(
                {
                    "relevance_score": None,
                    "outline_coverage": None,
                    "depth_score": None,
                    "continuity_score": None,
                }
            )
        self.validate_results.append(result)
        return result

    async def revise_chapter(
        self,
        spec: dict[str, Any],
        plan: dict[str, Any],
        sections: list[dict[str, Any]],
        content: str,
        validation: dict[str, Any],
        **_: Any,
    ) -> str:
        self._count("revise_chapter")
        self.revise_calls += 1
        return content + "\n\n" + _text(136)

    async def generate_introduction(
        self, spec: dict[str, Any], summaries: list[dict[str, Any]], **_: Any
    ) -> str:
        self._count("generate_introduction")
        return f"# Welcome\n\n{_text(100)}"

    async def generate_conclusion(
        self, spec: dict[str, Any], summaries: list[dict[str, Any]], **_: Any
    ) -> str:
        self._count("generate_conclusion")
        return f"# The Road Ahead\n\n{_text(90)}"

    async def validate_manuscript(
        self,
        spec: dict[str, Any],
        summaries: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        self._count("validate_manuscript")
        return {
            "ready_for_formatting": True,
            "overall_score": 88,
            "strengths": ["Consistent voice"],
            "weaknesses": [],
        }


async def _make_book(session: Any) -> tuple[User, WritingBook]:
    user = User(email="pipeline-test@example.com")
    session.add(user)
    await session.flush()
    wbook = WritingBook(user_id=user.id, title="AI Tools for Teachers")
    session.add(wbook)
    await session.flush()
    return user, wbook


def _setup_dict() -> dict[str, Any]:
    return {
        "details": {
            "title": "AI Tools for Teachers",
            "topic": "Practical AI tools for K-12 teachers",
            "language": "en",
        },
        # Small counts keep the test fast; chapters_override bypasses the
        # dynamic 6-8/8-12/12-20 range so only 3 chapters are produced.
        "size": {"total_word_count": 3000, "chapters_override": 3},
        "special_instructions": {"instructions": ""},
    }


async def _run_pipeline(session: Any, engine: FakeEngine, user_id: UUID, wbook: WritingBook):
    progress = ProgressRecorder()
    announce = AnnounceRecorder()
    pipe = GenerationPipeline(
        session,
        engine,
        user_id=user_id,
        wbook=wbook,
        setup=_setup_dict(),
        provider="fake-provider",
        model="fake-model",
        temperature=0.7,
        progress=progress,
        announce=announce,
    )
    summary = await pipe.run()
    return summary, progress, announce


# ---------------------------------------------------------------------------
# Pure-function coverage
# ---------------------------------------------------------------------------
def test_clamp_score_variants() -> None:
    assert _clamp_score(None) is None
    assert _clamp_score(True) == 100
    assert _clamp_score(False) == 0
    assert _clamp_score(85) == 85
    assert _clamp_score(85.9) == 85
    assert _clamp_score("72") == 72
    assert _clamp_score(" 63/100 ") == 63
    assert _clamp_score("n/a") is None
    assert _clamp_score("") is None
    assert _clamp_score(["high"]) is None
    assert _clamp_score(150) == 100
    assert _clamp_score(-5) == 0


def test_normalize_validation_reports_usable_scores() -> None:
    unusable = {"relevance_score": None, "outline_coverage": "n/a"}
    assert _normalize_validation(unusable, 4242) == []
    assert unusable["relevance_score"] is None
    assert unusable["word_count"] == 4242

    partial = {"relevance_score": "91/100", "outline_coverage": None}
    assert _normalize_validation(partial, 10) == ["relevance_score"]
    assert partial["relevance_score"] == 91
    assert partial["outline_coverage"] is None

    # Degenerate stub audit: everything zero with no findings counts as
    # "no audit" so it can never trigger revisions.
    stub = {
        "relevance_score": 0,
        "outline_coverage": 0,
        "depth_score": 0,
        "continuity_score": 0,
        "summary": "",
        "issues": [],
    }
    assert _normalize_validation(stub, 500) == []

    # Genuine harsh audit: zeros WITH findings stay a real (failing) audit.
    harsh = {
        "relevance_score": 5,
        "outline_coverage": 0,
        "depth_score": 10,
        "continuity_score": 0,
        "issues": ["Off-topic."],
    }
    assert _normalize_validation(harsh, 500) == [
        "relevance_score", "outline_coverage", "depth_score", "continuity_score",
    ]
    assert _audit_passed(harsh, _normalize_validation(harsh, 500), 500, 1000) is False


def test_audit_passed_gates_only_scored_dimensions() -> None:
    validation = {"relevance_score": 85, "outline_coverage": None}
    usable = _normalize_validation(validation, 700)
    # outline_coverage was never scored — it must not fail the chapter.
    assert _audit_passed(validation, usable, 700, 1000) is True
    # But the word-count floor still applies.
    assert _audit_passed(validation, usable, 100, 1000) is False


# ---------------------------------------------------------------------------
# Full-pipeline coverage
# ---------------------------------------------------------------------------
async def test_full_pipeline_happy_path(db_session: Any) -> None:
    user, wbook = await _make_book(db_session)
    engine = FakeEngine(validation_mode="pass")

    summary, progress, announce = await _run_pipeline(db_session, engine, user.id, wbook)

    # Specification locked with the user's constraints.
    assert summary["status"] == "ready_for_formatting"
    assert summary["chapter_count"] == 3
    assert wbook.target_word_count == 3000
    assert wbook.min_word_count == 2550
    assert wbook.max_word_count == 3600

    # Every section request carried the locked specification (topic lock).
    assert len(engine.section_specs) == 9  # 3 chapters x 3 sections
    for spec in engine.section_specs:
        assert spec["book_title"] == "AI Tools for Teachers"
        assert spec["topic"] == "Practical AI tools for K-12 teachers"
        assert spec["chapter_count"] == 3

    # Chapters written, validated, passed — no revisions needed.
    chapters = (
        (await db_session.execute(
            select(WritingChapter)
            .where(WritingChapter.book_id == wbook.id)
            .order_by(WritingChapter.chapter_number)
        ))
        .scalars()
        .all()
    )
    numbers = [c.chapter_number for c in chapters]
    assert numbers == [0, 1, 2, 3, 4]  # intro, 3 body chapters, conclusion

    body = [c for c in chapters if c.chapter_number in (1, 2, 3)]
    for ch in body:
        assert ch.status == "draft"
        assert ch.content
        assert ch.actual_word_count > 0
        assert len(ch.outline_sections) == 3
        assert ch.validation_result is not None
        assert ch.validation_result["passed"] is True
        assert ch.content_summary  # continuity feed for later chapters
        assert ch.revision_count == 0

    intro = next(c for c in chapters if c.chapter_number == 0)
    conclusion = next(c for c in chapters if c.chapter_number == 4)
    assert intro.title == "Introduction" and intro.content
    assert conclusion.title == "Conclusion" and conclusion.content

    # Manuscript assembled in order with front/back matter headings.
    manuscript = (
        await db_session.execute(select(Manuscript).where(Manuscript.book_id == wbook.id))
    ).scalar_one()
    assert "# Introduction" in manuscript.full_text
    assert "# Chapter 1:" in manuscript.full_text
    assert "# Conclusion" in manuscript.full_text
    assert manuscript.word_count > 0
    assert len(manuscript.chapter_order) == 5
    assert manuscript.is_stale is False

    # Quality report + book status.
    report = wbook.quality_report
    assert report is not None
    assert report["chapter_count"] == 3
    assert report["chapters_written"] == 5
    assert report["introduction_written"] is True
    assert report["conclusion_written"] is True
    assert report["failed_or_review_chapters"] == []
    assert report["ai_quality_report"]["overall_score"] == 88
    assert wbook.status == "ready_for_formatting"

    # Version snapshots exist for every generated chapter.
    versions = (
        await db_session.execute(select(ChapterVersion))
    ).scalars().all()
    assert len(versions) >= 5

    # Call-count sanity: one revision-free run.
    assert engine.calls["validate_chapter"] == 3
    assert engine.calls.get("revise_chapter", 0) == 0
    assert engine.calls["generate_introduction"] == 1
    assert engine.calls["generate_conclusion"] == 1
    assert engine.calls["validate_manuscript"] == 1
    assert progress.calls[-1][0] == 100

    # Activity timeline entries fired for outline + every chapter.
    assert announce.kinds.count("outline_created") == 1
    assert announce.kinds.count("chapter_generated") == 3


async def test_pipeline_auto_revises_failing_chapter(db_session: Any) -> None:
    user, wbook = await _make_book(db_session)
    engine = FakeEngine(validation_mode="fail_then_pass")

    summary, _, _ = await _run_pipeline(db_session, engine, user.id, wbook)

    assert summary["status"] == "ready_for_formatting"
    # Each chapter failed its first audit and was revised once.
    assert engine.revise_calls == 3

    body = (
        (await db_session.execute(
            select(WritingChapter).where(
                WritingChapter.book_id == wbook.id,
                WritingChapter.chapter_number.in_((1, 2, 3)),
            )
        ))
        .scalars()
        .all()
    )
    for ch in body:
        assert ch.status == "draft"
        assert ch.revision_count == 1
        assert ch.validation_result["revision_attempt"] == 1
        assert ch.validation_result["passed"] is True
        assert ch.actual_word_count >= 500  # revised content appended


async def test_pipeline_accepts_chapter_when_validation_unavailable(db_session: Any) -> None:
    """A malformed audit must not burn revisions or block the book."""
    user, wbook = await _make_book(db_session)
    engine = FakeEngine(validation_mode="unavailable")

    summary, _, _ = await _run_pipeline(db_session, engine, user.id, wbook)

    assert engine.calls["validate_chapter"] == 3
    assert engine.calls.get("revise_chapter", 0) == 0  # never revise on noise

    body = (
        (await db_session.execute(
            select(WritingChapter).where(
                WritingChapter.book_id == wbook.id,
                WritingChapter.chapter_number.in_((1, 2, 3)),
            )
        ))
        .scalars()
        .all()
    )
    for ch in body:
        assert ch.status == "draft"
        assert ch.validation_result["validation_unavailable"] is True
        assert ch.validation_result["passed"] is True
        assert ch.content  # content preserved as-is


async def test_pipeline_resume_skips_completed_stages(db_session: Any) -> None:
    user, wbook = await _make_book(db_session)
    engine = FakeEngine(validation_mode="pass")

    await _run_pipeline(db_session, engine, user.id, wbook)
    baseline = dict(engine.calls)

    # Second run must not redo any completed work.
    await _run_pipeline(db_session, engine, user.id, wbook)

    after = engine.calls
    for stage in (
        "generate_specification",
        "generate_blueprint_from_spec",
        "generate_chapter_outline_from_spec",
        "generate_chapter_section",
        "validate_chapter",
        "generate_introduction",
        "generate_conclusion",
    ):
        assert after.get(stage, 0) == baseline.get(stage, 0), stage

    # Still exactly 5 chapters (no duplicates on resume).
    chapters = (
        await db_session.execute(
            select(WritingChapter).where(WritingChapter.book_id == wbook.id)
        )
    ).scalars().all()
    assert sorted(c.chapter_number for c in chapters) == [0, 1, 2, 3, 4]


async def test_regenerate_single_chapter(db_session: Any) -> None:
    user, wbook = await _make_book(db_session)
    engine = FakeEngine(validation_mode="pass")
    await _run_pipeline(db_session, engine, user.id, wbook)
    sections_before = engine.calls["generate_chapter_section"]

    target = (
        await db_session.execute(
            select(WritingChapter).where(
                WritingChapter.book_id == wbook.id,
                WritingChapter.chapter_number == 2,
            )
        )
    ).scalar_one()

    rewritten = await regenerate_chapter(
        db_session,
        engine,
        user_id=user.id,
        wbook=wbook,
        chapter_number=2,
        provider="fake-provider",
        model="fake-model",
    )

    assert rewritten.chapter_number == 2
    assert rewritten.status == "draft"
    assert rewritten.content
    assert rewritten.validation_result["passed"] is True
    assert rewritten.revision_count == 0
    # Only the target chapter's sections were re-written.
    assert engine.calls["generate_chapter_section"] == sections_before + 3

    # A new version snapshot was created.
    versions = (
        await db_session.execute(
            select(ChapterVersion).where(ChapterVersion.chapter_id == rewritten.id)
        )
    ).scalars().all()
    assert len(versions) == 2


class _FallbackCountingAI:
    """Stands in for AIService's fallback-usage accounting."""

    def __init__(self, pending: int) -> None:
        self._pending = pending
        self.consumed_for: list[Any] = []

    def consume_fallback_count(self, book_id: Any) -> int:
        self.consumed_for.append(book_id)
        count, self._pending = self._pending, 0
        return count


async def test_pipeline_flags_book_when_fallback_served_content(db_session: Any) -> None:
    """Offline-fallback content must never be reported as ready."""
    user, wbook = await _make_book(db_session)
    engine = FakeEngine(validation_mode="pass")
    engine.ai = _FallbackCountingAI(pending=7)

    summary = await _run_pipeline(db_session, engine, user.id, wbook)
    summary = summary[0]

    assert engine.ai.consumed_for == [wbook.id]
    report = wbook.quality_report or {}
    assert report["fallback_generated_units"] == 7
    assert report["degraded"] is True
    assert wbook.status == "needs_review"
    assert summary["status"] == "needs_review"


async def test_pipeline_filters_reserved_back_matter_from_blueprint(db_session: Any) -> None:
    """Blueprint entries titled Introduction/Conclusion become back matter, not body chapters."""
    user, wbook = await _make_book(db_session)
    engine = FakeEngine(validation_mode="pass")

    original_blueprint = FakeEngine.generate_blueprint_from_spec

    async def blueprint_with_back_matter(self, spec, **_):
        payload = await original_blueprint(self, spec)
        payload["chapters"] = [
            {"title": "Introduction: Why AI Now", "objective": "hook",
             "summary": "intro", "estimated_word_count": 500},
            *payload["chapters"],
            {"title": "Conclusion: Embracing AI for a Brighter Future",
             "objective": "commit", "summary": "wrap up", "estimated_word_count": 500},
        ]
        return payload

    engine.generate_blueprint_from_spec = blueprint_with_back_matter.__get__(engine)

    await _run_pipeline(db_session, engine, user.id, wbook)

    chapters = (
        await db_session.execute(
            select(WritingChapter).where(WritingChapter.book_id == wbook.id)
        )
    ).scalars().all()
    titles = [c.title or "" for c in chapters]
    # The blueprint's reserved entries were dropped: body chapters are exactly
    # 1..3 (the spec's chapter_count), plus one intro and one pipeline-written
    # conclusion — no "Conclusion: ..." duplicate and no stray Introduction.
    assert sorted(c.chapter_number for c in chapters) == [0, 1, 2, 3, 4]
    assert not any("Why AI Now" in t for t in titles), titles
    assert not any("Embracing AI" in t for t in titles), titles
    assert sum(1 for t in titles if is_conclusion_title(t)) == 1
