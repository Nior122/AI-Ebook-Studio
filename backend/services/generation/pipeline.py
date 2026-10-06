"""Phase 6 repair — the multi-stage book generation pipeline.

This module replaces the old "one prompt per chapter" flow with a real book
production pipeline:

    1. Specification   — lock the book definition (TOPIC LOCK)
    2. Blueprint       — chapter-by-chapter architecture from the spec
    3. Outlines        — section-level plan for every chapter
    4. Writing         — each chapter written ONE SECTION AT A TIME
    5. Validation      — relevance / coverage / depth / continuity audit
    6. Revision        — targeted fixes (max 3), then ``needs_review``
    7. Intro/Conclusion— written LAST from the real chapter summaries
    8. Manuscript      — assembly + book-level quality report

Every stage is resume-friendly: re-running the pipeline skips completed work
(spec, blueprint, outlined chapters, written chapters, intro/conclusion) and
continues where an interrupted run stopped.

The pipeline never talks to a provider directly — all AI calls go through
:class:`BookWritingEngine`, which uses the provider-agnostic ``AIService``.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.book_writing import (
    BookBlueprint,
    BookBrief,
    BookSpecification,
    WritingBook,
    WritingBookSettings,
    WritingChapter,
)
from services.book_writing.context import StyleProfile
from services.book_writing.engine import BookWritingEngine

logger = logging.getLogger("api.generation.pipeline")


# ---------------------------------------------------------------------------
# Validation thresholds (0-100)
# ---------------------------------------------------------------------------
RELEVANCE_THRESHOLD = 70
COVERAGE_THRESHOLD = 70
DEPTH_THRESHOLD = 60
CONTINUITY_THRESHOLD = 60
MAX_REVISIONS = 3


def _wc(text: str | None) -> int:
    return len(re.findall(r"\S+", text or ""))


WORD_COUNT_MIN_RATIO = 0.80
WORD_COUNT_MAX_RATIO = 1.20


def _front_matter_word_target(target_word_count: int) -> int:
    """Reserve a measured share of the total target for intro and conclusion."""
    if target_word_count <= 0:
        return 0
    # Keep front/back matter concise in long books and proportional in short
    # books so body chapter budgets still add up to the user's total target.
    return min(
        1500, max(1, min(int(target_word_count * 0.15), max(60, round(target_word_count * 0.06))))
    )


def _allocate_chapter_word_targets(
    plans: list[dict[str, Any]], target_word_count: int
) -> list[int]:
    """Allocate the body-word budget across chapters using blueprint weights."""
    if not plans:
        return []
    front_matter = _front_matter_word_target(target_word_count)
    body_target = max(0, target_word_count - 2 * front_matter)
    weights = [max(1, int(plan.get("estimated_word_count") or 1)) for plan in plans]
    total_weight = sum(weights)
    targets = [body_target * weight // total_weight for weight in weights]
    remainder = body_target - sum(targets)
    for index in range(remainder):
        targets[index % len(targets)] += 1
    return targets


def _word_count_range(target_word_count: int) -> tuple[int, int]:
    target = max(0, int(target_word_count))
    return (
        int(target * WORD_COUNT_MIN_RATIO),
        int(target * WORD_COUNT_MAX_RATIO),
    )


def _normalized_title(title: str | None) -> str:
    if not title:
        return ""
    return title.strip().strip("#:.!?—–- \t").lower()


def is_introduction_title(title: str | None) -> bool:
    """True for Introduction-style titles the pipeline reserves for chapter 0."""
    return _normalized_title(title).startswith("introduction")


def is_conclusion_title(title: str | None) -> bool:
    """True for Conclusion-style titles the pipeline reserves as back matter.

    Blueprints often emit entries like "Conclusion: Embracing Change"; those
    must not become body chapters or the conclusion stage appends a duplicate.
    """
    normalized = _normalized_title(title)
    return normalized.startswith(("conclusion", "final thoughts", "closing thoughts", "epilogue"))


def _clamp_score(value: Any) -> int | None:
    """Parse a model score into 0-100. Returns ``None`` when unusable.

    Models sometimes emit ``"85"``, ``"85/100"``, ``85.0`` or ``null``; we accept
    anything numeric and reject the rest so a malformed audit cannot silently
    force expensive revisions.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return 100 if value else 0
    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))
    if isinstance(value, str):
        text = value.strip().split("/", 1)[0].strip()
        try:
            return max(0, min(100, int(float(text))))
        except ValueError:
            return None
    return None


_SCORE_KEYS = (
    ("relevance_score", RELEVANCE_THRESHOLD),
    ("outline_coverage", COVERAGE_THRESHOLD),
    ("depth_score", DEPTH_THRESHOLD),
    ("continuity_score", CONTINUITY_THRESHOLD),
)


def _normalize_validation(validation: dict[str, Any], word_count: int) -> list[str]:
    """Coerce the audit's scores in place.

    Returns the list of keys that carried a usable score. Missing/unparseable
    dimensions stay ``None`` and are treated as an incomplete audit by the
    validation gate; they can never silently count as a pass.
    """
    usable: list[str] = []
    for key, _threshold in _SCORE_KEYS:
        score = _clamp_score(validation.get(key))
        validation[key] = score
        if score is not None:
            usable.append(key)
    validation["word_count"] = word_count

    # Degenerate-audit guard: a stub/fallback response scores everything 0
    # with no findings. Treating that as real "0/100" would trigger pointless
    # revisions — treat it as no audit at all.
    if usable and all(validation[k] == 0 for k in usable):
        has_findings = bool(
            validation.get("issues")
            or validation.get("missing_sections")
            or (validation.get("summary") or "").strip()
        )
        if not has_findings:
            return []

    return usable


def _audit_passed(
    validation: dict[str, Any], usable: list[str], word_count: int, target_wc: int
) -> bool:
    """Require a complete audit, passing scores, and realistic chapter length."""
    required = {key for key, _threshold in _SCORE_KEYS}
    if not required.issubset(usable):
        return False
    thresholds = dict(_SCORE_KEYS)
    if any(validation[key] < thresholds[key] for key in required):
        return False
    minimum, maximum = _word_count_range(target_wc)
    return minimum <= word_count <= maximum


# ---------------------------------------------------------------------------
# Specification helpers
# ---------------------------------------------------------------------------
def spec_to_dict(spec: BookSpecification) -> dict[str, Any]:
    """Serialize a BookSpecification row into the dict prompts consume."""
    return {
        "book_title": spec.book_title,
        "subtitle": spec.subtitle,
        "topic": spec.topic,
        "description": spec.description,
        "target_audience": spec.target_audience,
        "book_type": spec.book_type,
        "language": spec.language,
        "tone": spec.tone,
        "main_promise": spec.main_promise,
        "reader_problem": spec.reader_problem,
        "reader_transformation": spec.reader_transformation,
        "key_topics": list(spec.key_topics or []),
        "required_topics": list(spec.required_topics or []),
        "excluded_topics": list(spec.excluded_topics or []),
        "chapter_count": spec.chapter_count,
        "target_word_count": spec.target_word_count,
        "writing_style": spec.writing_style,
        "difficulty_level": spec.difficulty_level,
        "practical_focus": spec.practical_focus,
        "special_instructions": spec.special_instructions,
    }


async def load_specification(
    session: AsyncSession, book_id: UUID
) -> BookSpecification | None:
    result = await session.execute(
        select(BookSpecification).where(
            BookSpecification.book_id == book_id,
            BookSpecification.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


def _normalize_spec_data(data: dict[str, Any], setup: dict[str, Any]) -> dict[str, Any]:
    """Clamp/repair the AI-produced specification against the user's request."""
    details = setup.get("details", {}) or {}
    size = setup.get("size", {}) or {}

    requested_words = int(size.get("total_word_count") or 10000)
    target_words = int(data.get("target_word_count") or requested_words)
    # Never let the model inflate/deflate the book by more than 25%.
    target_words = max(int(requested_words * 0.75), min(int(requested_words * 1.25), target_words))

    requested_chapters = size.get("chapters_override")
    if requested_chapters:
        chapter_count = int(requested_chapters)
    else:
        chapter_count = int(data.get("chapter_count") or 0)
        # Dynamic chapter count by length (spec: 6-8 / 8-12 / 12-20).
        if target_words <= 10000:
            chapter_count = max(6, min(8, chapter_count or 8))
        elif target_words <= 25000:
            chapter_count = max(8, min(12, chapter_count or 10))
        else:
            chapter_count = max(12, min(20, chapter_count or 14))

    return {
        **data,
        "book_title": str(data.get("book_title") or details.get("title") or "Untitled"),
        "topic": str(data.get("topic") or details.get("topic") or ""),
        "language": str(data.get("language") or details.get("language") or "en"),
        "target_word_count": target_words,
        "chapter_count": chapter_count,
        "key_topics": [str(t) for t in (data.get("key_topics") or [])][:15],
        "required_topics": [str(t) for t in (data.get("required_topics") or [])][:10],
        "excluded_topics": [str(t) for t in (data.get("excluded_topics") or [])][:10],
    }


async def upsert_specification(
    session: AsyncSession, book: WritingBook, data: dict[str, Any]
) -> BookSpecification:
    result = await session.execute(
        select(BookSpecification).where(BookSpecification.book_id == book.id)
    )
    spec = result.scalar_one_or_none()
    if spec is None:
        spec = BookSpecification(
            book_id=book.id,
            book_title=data["book_title"],
            topic=data["topic"],
        )
        session.add(spec)

    spec.book_title = data.get("book_title") or spec.book_title
    spec.subtitle = data.get("subtitle")
    spec.topic = data.get("topic") or spec.topic
    spec.description = data.get("description")
    spec.target_audience = data.get("target_audience")
    spec.book_type = data.get("book_type")
    spec.language = data.get("language") or "en"
    spec.tone = data.get("tone")
    spec.main_promise = data.get("main_promise")
    spec.reader_problem = data.get("reader_problem")
    spec.reader_transformation = data.get("reader_transformation")
    spec.key_topics = data.get("key_topics") or []
    spec.required_topics = data.get("required_topics") or []
    spec.excluded_topics = data.get("excluded_topics") or []
    spec.chapter_count = int(data.get("chapter_count") or 10)
    spec.target_word_count = int(data.get("target_word_count") or 10000)
    spec.min_word_count = int(spec.target_word_count * 0.85)
    spec.max_word_count = int(spec.target_word_count * 1.2)
    spec.writing_style = data.get("writing_style")
    spec.difficulty_level = data.get("difficulty_level")
    spec.practical_focus = bool(data.get("practical_focus", True))
    spec.special_instructions = data.get("special_instructions")

    # Mirror the lock onto the book row (word-count management + identity).
    book.target_word_count = spec.target_word_count
    book.min_word_count = spec.min_word_count
    book.max_word_count = spec.max_word_count
    if spec.subtitle and not book.subtitle:
        book.subtitle = spec.subtitle
    if spec.target_audience and not book.target_audience:
        book.target_audience = spec.target_audience
    if spec.tone and not book.tone:
        book.tone = spec.tone

    await session.flush()
    return spec


# ---------------------------------------------------------------------------
# Style guidance
# ---------------------------------------------------------------------------
async def get_style_guidance(session: AsyncSession, book_id: UUID) -> str:
    result = await session.execute(
        select(WritingBookSettings).where(
            WritingBookSettings.book_id == book_id,
            WritingBookSettings.deleted_at.is_(None),
        )
    )
    settings = result.scalar_one_or_none()
    return StyleProfile.from_settings(settings).to_guidance()


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------
class GenerationPipeline:
    """Drives the full multi-stage generation for one book.

    All state is persisted as it is produced, so the same entry point serves
    both first-run generation and resume.
    """

    def __init__(
        self,
        session: AsyncSession,
        engine: BookWritingEngine,
        *,
        user_id: UUID,
        wbook: WritingBook,
        setup: dict[str, Any],
        provider: str | None,
        model: str | None,
        temperature: float,
        progress: Any,
        announce: Any = None,
    ) -> None:
        self.session = session
        self.engine = engine
        self.user_id = user_id
        self.wbook = wbook
        self.setup = setup
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.progress = progress
        # Optional async (kind, message) sink for the project activity timeline.
        self.announce = announce

    async def _announce(self, kind: str, message: str) -> None:
        if self.announce is not None:
            try:
                await self.announce(kind, message)
            except Exception as exc:  # noqa: BLE001 — timeline entries are best-effort
                logger.warning("Activity announcement failed (%s): %s", kind, exc)

    # ------------------------------------------------------------------
    # state helpers
    # ------------------------------------------------------------------
    def _state(self) -> dict[str, Any]:
        state = dict(self.wbook.generation_state or {})
        return state

    async def _save_state(self, **updates: Any) -> None:
        state = self._state()
        state.update(updates)
        # SQLAlchemy JSON columns need reassignment to mark dirty.
        self.wbook.generation_state = {**state}
        await self.session.flush()

    async def _ai(self, method: str, *args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("provider", self.provider)
        kwargs.setdefault("model", self.model)
        kwargs.setdefault("user_id", self.user_id)
        kwargs.setdefault("book_id", self.wbook.id)
        return await getattr(self.engine, method)(*args, **kwargs)

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------
    async def run(self) -> dict[str, Any]:
        """Run (or resume) the full pipeline. Returns the summary dict."""
        spec = await self._stage_specification()
        spec_dict = spec_to_dict(spec)
        style = await get_style_guidance(self.session, self.wbook.id)

        blueprint = await self._stage_blueprint(spec_dict, style)
        chapters = await self._stage_outlines(spec_dict, blueprint, style)

        await self._stage_write_chapters(spec_dict, blueprint, chapters, style)

        await self._stage_intro_conclusion(spec_dict, blueprint, style)

        summary = await self._stage_finalize(spec_dict)
        return summary

    # ------------------------------------------------------------------
    # stage 1: specification (topic lock)
    # ------------------------------------------------------------------
    async def _stage_specification(self) -> BookSpecification:
        existing = await load_specification(self.session, self.wbook.id)
        if existing is not None:
            await self.progress(8, "Book specification locked — resuming")
            return existing

        await self.progress(3, "Analyzing your book idea")
        self.wbook.status = "planning"
        self.wbook.current_step = "brief"
        await self._save_state(stage="specification")

        setup = dict(self.setup)
        data = await self._ai("generate_specification", setup, temperature=0.5)
        data = _normalize_spec_data(data if isinstance(data, dict) else {}, setup)
        data.setdefault(
            "special_instructions",
            (self.setup.get("special_instructions", {}) or {}).get("instructions", ""),
        )
        spec = await upsert_specification(self.session, self.wbook, data)

        # Keep the editor-facing Brief in sync (cheap, reuses existing flow).
        brief_result = await self.session.execute(
            select(BookBrief).where(BookBrief.book_id == self.wbook.id)
        )
        if brief_result.scalar_one_or_none() is None:
            brief = BookBrief(
                book_id=self.wbook.id,
                working_title=spec.book_title,
                subtitle=spec.subtitle,
                book_purpose=spec.main_promise,
                target_reader=spec.target_audience,
                reader_problems=[spec.reader_problem] if spec.reader_problem else [],
                promised_transformation=spec.reader_transformation,
                tone=spec.tone,
                writing_style=spec.writing_style,
                key_themes=list(spec.key_topics or []),
                major_concepts=list(spec.required_topics or []),
                topics_to_avoid=list(spec.excluded_topics or []),
                estimated_chapter_count=spec.chapter_count,
                estimated_word_count=spec.target_word_count,
            )
            self.session.add(brief)

        await self.session.commit()
        await self.progress(8, "Book specification locked")
        return spec

    # ------------------------------------------------------------------
    # stage 2: blueprint
    # ------------------------------------------------------------------
    async def _stage_blueprint(
        self, spec_dict: dict[str, Any], style: str
    ) -> BookBlueprint:
        result = await self.session.execute(
            select(BookBlueprint).where(
                BookBlueprint.book_id == self.wbook.id,
                BookBlueprint.deleted_at.is_(None),
            )
        )
        blueprint = result.scalar_one_or_none()
        if blueprint is not None and blueprint.chapters:
            await self.progress(16, "Blueprint ready — resuming")
            return blueprint

        await self.progress(10, "Designing the chapter blueprint")
        self.wbook.current_step = "blueprint"
        await self._save_state(stage="blueprint")

        data = await self._ai(
            "generate_blueprint_from_spec", spec_dict,
            style_guidance=style, temperature=0.6,
        )
        data = data if isinstance(data, dict) else {}
        chapters = [c for c in (data.get("chapters") or []) if isinstance(c, dict)]
        # The pipeline reserves Introduction (chapter 0) and a trailing
        # conclusion as back matter and writes them itself; blueprint entries
        # with those titles must be dropped BEFORE the locked-count trim so
        # they cannot displace real body chapters.
        reserved = [
            str(c.get("title", ""))
            for c in chapters
            if is_introduction_title(c.get("title")) or is_conclusion_title(c.get("title"))
        ]
        if reserved:
            logger.info(
                "Dropping %d reserved back-matter outline(s) from blueprint: %s",
                len(reserved), reserved,
            )
            chapters = [
                c
                for c in chapters
                if not (
                    is_introduction_title(c.get("title"))
                    or is_conclusion_title(c.get("title"))
                )
            ]
        if not chapters:
            raise RuntimeError("Blueprint generation returned no chapters.")

        # Never silently under-deliver the chapter count locked in the spec.
        # An incomplete blueprint fails with its spec/checkpoint persisted so a
        # retry can recover without presenting a partial manuscript as done.
        wanted = int(spec_dict.get("chapter_count") or len(chapters))
        if len(chapters) < wanted:
            raise RuntimeError(
                f"Blueprint returned {len(chapters)} of {wanted} requested chapters. "
                "Retry blueprint generation before writing the manuscript."
            )
        chapters = chapters[:wanted]

        if blueprint is None:
            blueprint = BookBlueprint(book_id=self.wbook.id)
            self.session.add(blueprint)
        blueprint.introduction_purpose = data.get("introduction_purpose")
        blueprint.chapters = chapters
        blueprint.estimated_total_word_count = int(
            data.get("estimated_total_word_count") or spec_dict.get("target_word_count") or 0
        )
        # Store the conclusion purpose alongside (JSON extension).
        conclusion_purpose = data.get("conclusion_purpose") or ""
        if conclusion_purpose:
            blueprint.introduction_purpose = (
                blueprint.introduction_purpose or ""
            )
            # keep conclusion purpose in generation_state to avoid schema change
            await self._save_state(conclusion_purpose=conclusion_purpose)

        self.wbook.current_step = "outline"
        await self.session.commit()
        await self.progress(16, f"Blueprint complete — {len(chapters)} chapters planned")
        return blueprint

    # ------------------------------------------------------------------
    # stage 3: chapter creation + outlines
    # ------------------------------------------------------------------
    async def _stage_outlines(
        self,
        spec_dict: dict[str, Any],
        blueprint: BookBlueprint,
        style: str,
    ) -> list[WritingChapter]:
        await self.progress(18, "Preparing chapter outlines")
        self.wbook.status = "outlining"
        await self._save_state(stage="outlines")

        plans = list(blueprint.chapters or [])
        # The pipeline reserves Introduction (chapter 0) and a trailing
        # conclusion as back matter and writes them itself; blueprint entries
        # with those titles must not become numbered body chapters.
        reserved = [
            str(p.get("title", ""))
            for p in plans
            if is_introduction_title(p.get("title")) or is_conclusion_title(p.get("title"))
        ]
        if reserved:
            logger.info(
                "Dropping %d reserved back-matter outline(s) from blueprint: %s",
                len(reserved), reserved,
            )
            plans = [
                p
                for p in plans
                if not (
                    is_introduction_title(p.get("title"))
                    or is_conclusion_title(p.get("title"))
                )
            ]
        total = len(plans)
        if total == 0:
            raise RuntimeError("The blueprint contains no body chapters to outline.")
        target_total = int(spec_dict.get("target_word_count") or 10000)
        chapter_word_targets = _allocate_chapter_word_targets(plans, target_total)
        titles = [str(p.get("title", f"Chapter {i + 1}")) for i, p in enumerate(plans)]

        # Load existing chapters (resume).
        result = await self.session.execute(
            select(WritingChapter).where(
                WritingChapter.book_id == self.wbook.id,
                WritingChapter.deleted_at.is_(None),
                WritingChapter.chapter_number.between(1, total),
            )
        )
        by_number = {ch.chapter_number: ch for ch in result.scalars().all()}

        chapters: list[WritingChapter] = []
        for i, plan in enumerate(plans):
            number = i + 1
            title = titles[i]
            target_wc = chapter_word_targets[i]

            chapter = by_number.get(number)
            if chapter is None:
                chapter = WritingChapter(
                    book_id=self.wbook.id,
                    chapter_number=number,
                    title=title,
                    status="planned",
                )
                self.session.add(chapter)
                await self.session.flush()

            chapter.title = title
            chapter.purpose = str(plan.get("objective", "") or "")
            chapter.objective = str(plan.get("summary", "") or "")[:2000]
            chapter.summary = str(plan.get("summary", "") or "")[:2000]
            chapter.target_word_count = target_wc

            if not chapter.outline_sections:
                pct = int(18 + (6 * (i + 1) / max(total, 1)))
                await self.progress(min(pct, 24), f"Outlining Chapter {number}: {title[:50]}")
                try:
                    outline = await self._ai(
                        "generate_chapter_outline_from_spec",
                        spec_dict, plan,
                        chapter_number=number,
                        total_chapters=total,
                        target_word_count=target_wc,
                        blueprint_titles=titles,
                        style_guidance=style,
                        temperature=0.5,
                    )
                    sections = [
                        {
                            "title": str(s.get("title", "")),
                            "purpose": str(s.get("purpose", "") or ""),
                            "key_points": [str(k) for k in (s.get("key_points") or [])][:8],
                        }
                        for s in ((outline or {}).get("sections") or [])
                        if isinstance(s, dict) and s.get("title")
                    ]
                except Exception as exc:  # noqa: BLE001 — outline failure is recoverable
                    logger.warning("Outline failed for chapter %d: %s", number, exc)
                    sections = []
                if not sections:
                    # Deterministic fallback so writing can always proceed.
                    sections = [
                        {
                            "title": "Opening: what this chapter covers",
                            "purpose": "Hook the reader and frame the chapter.",
                            "key_points": [str(plan.get("objective", ""))][:1],
                        },
                        {
                            "title": str(plan.get("title", "Core material")),
                            "purpose": "Deliver the chapter's core teaching.",
                            "key_points": [str(k) for k in (plan.get("key_lessons") or [])][:6],
                        },
                        {
                            "title": "Putting it into practice",
                            "purpose": "Concrete application of the chapter.",
                            "key_points": [
                                str(e) for e in (plan.get("practical_exercises") or [])
                            ][:4]
                            or ["Apply the key ideas step by step."],
                        },
                        {
                            "title": "Chapter wrap-up",
                            "purpose": "Recap and transition to the next chapter.",
                            "key_points": ["Summarize the key takeaways."],
                        },
                    ]
                chapter.outline_sections = sections
                chapter.outline = "\n".join(
                    f"{s['title']}: " + "; ".join(s.get("key_points", [])) for s in sections
                )
                chapter.status = "outlining"
                await self.session.commit()

            chapters.append(chapter)

        await self.session.commit()
        await self.progress(24, "All chapter outlines ready")
        await self._announce(
            "outline_created", f"Blueprint ready — {total} chapters outlined"
        )
        return chapters

    # ------------------------------------------------------------------
    # stage 4-6: write each chapter section-by-section, validate, revise
    # ------------------------------------------------------------------
    async def _stage_write_chapters(
        self,
        spec_dict: dict[str, Any],
        blueprint: BookBlueprint,
        chapters: list[WritingChapter],
        style: str,
    ) -> None:
        self.wbook.status = "generating"
        self.wbook.current_step = "writing"
        await self._save_state(stage="writing")

        total = len(chapters)
        spread_start, spread_end = 24, 86
        per = (spread_end - spread_start) / max(total, 1)
        plans = list(blueprint.chapters or [])

        previous_summary = ""
        for idx, chapter in enumerate(chapters):
            plan = plans[idx] if idx < len(plans) else {"title": chapter.title}

            # Resume: finished chapters are kept untouched.
            if chapter.content and chapter.status in ("draft", "approved", "needs_review"):
                previous_summary = chapter.content_summary or chapter.summary or ""
                pct = int(spread_start + per * (idx + 1))
                await self.progress(
                    pct,
                    f"Chapter {chapter.chapter_number} already written — skipping",
                )
                continue

            pct = int(spread_start + per * idx)
            await self.progress(
                pct, f"Writing Chapter {chapter.chapter_number}/{total}: {chapter.title[:48]}"
            )
            chapter.status = "generating"
            await self.session.flush()

            try:
                content = await self._write_chapter_sections(
                    spec_dict, plan, chapter, style, previous_summary, total
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Chapter %d generation failed", chapter.chapter_number)
                chapter.status = "failed"
                chapter.content = ""
                await self.session.commit()
                await self._save_state(
                    last_error=f"Chapter {chapter.chapter_number} failed: {exc}"
                )
                continue

            # Validate + revise loop (may return revised content).
            validation = await self._validate_and_revise(
                spec_dict, plan, chapter, content, style, previous_summary
            )
            content = validation.pop("content", content)

            chapter.content = content
            chapter.actual_word_count = _wc(content)
            chapter.validation_result = validation
            chapter.content_summary = str(validation.get("summary") or "")[:1500] or chapter.summary
            chapter.status = "draft" if validation.get("passed") else "needs_review"
            chapter.is_approved = False
            await self._snapshot_version(chapter, content)
            await self.session.commit()

            previous_summary = chapter.content_summary or ""
            pct = int(spread_start + per * (idx + 1))
            await self.progress(
                pct,
                f"Chapter {chapter.chapter_number} done — "
                f"{chapter.actual_word_count:,} words"
                + ("" if validation.get("passed") else " (flagged for review)"),
            )
            await self._announce(
                "chapter_generated",
                f"Chapter {chapter.chapter_number} written — "
                f"{chapter.actual_word_count:,} words"
                + ("" if validation.get("passed") else " — flagged for review"),
            )

        await self.progress(spread_end, "All chapters written")

    async def _write_chapter_sections(
        self,
        spec_dict: dict[str, Any],
        plan: dict[str, Any],
        chapter: WritingChapter,
        style: str,
        previous_summary: str,
        total_chapters: int,
    ) -> str:
        sections = list(chapter.outline_sections or [])
        if not sections:
            raise RuntimeError("Chapter has no outline sections.")

        target_wc = chapter.target_word_count or 1000
        per_section = max(1, target_wc // len(sections))

        written: list[dict[str, Any]] = []
        parts: list[str] = []
        for i, section in enumerate(sections):
            text = await self._ai(
                "generate_chapter_section",
                spec_dict,
                plan,
                sections,
                i,
                chapter_number=chapter.chapter_number,
                total_chapters=total_chapters,
                section_word_target=per_section,
                previous_chapter_summary=previous_summary if i == 0 else "",
                written_sections=written[-3:],  # bounded continuity window
                style_guidance=style,
                temperature=self.temperature,
            )
            text = (text or "").strip()
            if not text:
                continue
            parts.append(text)
            written.append({"title": section.get("title", ""), "content_tail": text[-1200:]})

        if not parts:
            raise RuntimeError("All section generations returned empty content.")
        return "\n\n".join(parts)

    async def _validate_and_revise(
        self,
        spec_dict: dict[str, Any],
        plan: dict[str, Any],
        chapter: WritingChapter,
        content: str,
        style: str,
        previous_summary: str,
    ) -> dict[str, Any]:
        target_wc = chapter.target_word_count or 1000
        validation: dict[str, Any] = {}

        for attempt in range(MAX_REVISIONS + 1):
            try:
                validation = await self._ai(
                    "validate_chapter",
                    spec_dict,
                    plan,
                    list(chapter.outline_sections or []),
                    content,
                    chapter_number=chapter.chapter_number,
                    target_word_count=target_wc,
                    previous_chapter_summary=previous_summary,
                    temperature=0.2,
                )
            except Exception as exc:  # noqa: BLE001 — validation is best-effort
                logger.warning("Validation failed for chapter %d: %s", chapter.chapter_number, exc)
                validation = {}

            validation = validation if isinstance(validation, dict) else {}
            usable_scores = _normalize_validation(validation, _wc(content))

            issues = [str(i) for i in (validation.get("issues") or [])]
            minimum_words, maximum_words = _word_count_range(target_wc)
            if not minimum_words <= validation["word_count"] <= maximum_words:
                direction = "below" if validation["word_count"] < minimum_words else "above"
                issues.append(
                    f"Chapter is {validation['word_count']:,} words, {direction} the allowed "
                    f"{minimum_words:,}–{maximum_words:,} word range for its "
                    f"{target_wc:,} word target."
                )
                validation["issues"] = issues

            required_scores = {key for key, _threshold in _SCORE_KEYS}
            if not required_scores.issubset(usable_scores):
                # Missing semantic scores are not a pass. Preserve the draft,
                # avoid blind auto-revisions, and make the review requirement
                # visible so a real provider or author can complete it later.
                validation["passed"] = False
                validation["validation_unavailable"] = True
                validation["missing_scores"] = sorted(required_scores - set(usable_scores))
                validation["revision_attempt"] = attempt
                logger.warning(
                    "Validation unavailable or incomplete for chapter %d — "
                    "keeping draft for review",
                    chapter.chapter_number,
                )
                break

            passed = _audit_passed(validation, usable_scores, validation["word_count"], target_wc)
            validation["passed"] = passed
            validation["revision_attempt"] = attempt

            if passed or attempt >= MAX_REVISIONS:
                break

            # Auto-revision using the audit findings.
            logger.info(
                "Revising chapter %d (attempt %d/%d): relevance=%s "
                "coverage=%s depth=%s continuity=%s",
                chapter.chapter_number, attempt + 1, MAX_REVISIONS,
                validation["relevance_score"], validation["outline_coverage"],
                validation["depth_score"], validation["continuity_score"],
            )
            try:
                revised = await self._ai(
                    "revise_chapter",
                    spec_dict,
                    plan,
                    list(chapter.outline_sections or []),
                    content,
                    validation,
                    chapter_number=chapter.chapter_number,
                    target_word_count=target_wc,
                    style_guidance=style,
                    temperature=0.7,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Revision failed for chapter %d: %s", chapter.chapter_number, exc)
                break
            if revised and revised.strip():
                content = revised.strip()
                chapter.revision_count = attempt + 1
                await self.session.flush()

        validation["content"] = content
        return validation

    async def _snapshot_version(self, chapter: WritingChapter, content: str) -> None:
        from models.book_writing import ChapterVersion

        result = await self.session.execute(
            select(ChapterVersion.version_number)
            .where(ChapterVersion.chapter_id == chapter.id)
            .order_by(ChapterVersion.version_number.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none() or 0
        self.session.add(
            ChapterVersion(
                chapter_id=chapter.id,
                version_number=last + 1,
                content=content,
                word_count=_wc(content),
                version_type="ai_generated",
                generation_metadata={
                    "provider": self.provider,
                    "model": self.model,
                    "task": "pipeline_generation",
                    "validation": {
                        k: v for k, v in (chapter.validation_result or {}).items() if k != "content"
                    },
                },
                created_by=self.user_id,
            )
        )

    # ------------------------------------------------------------------
    # stage 7: introduction + conclusion (written LAST)
    # ------------------------------------------------------------------
    async def _stage_intro_conclusion(
        self,
        spec_dict: dict[str, Any],
        blueprint: BookBlueprint,
        style: str,
    ) -> None:
        await self.progress(88, "Writing introduction and conclusion")
        await self._save_state(stage="intro_conclusion")

        result = await self.session.execute(
            select(WritingChapter).where(
                WritingChapter.book_id == self.wbook.id,
                WritingChapter.deleted_at.is_(None),
            ).order_by(WritingChapter.chapter_number)
        )
        all_chapters = list(result.scalars().all())
        body_chapters = [c for c in all_chapters if c.chapter_number >= 1 and c.content]

        summaries = [
            {
                "chapter_number": c.chapter_number,
                "title": c.title,
                "summary": (c.content_summary or c.summary or "")[:400],
                "word_count": c.actual_word_count or 0,
            }
            for c in body_chapters
        ]
        if not summaries:
            return

        # An existing conclusion (found by its reserved title) must be reused on
        # resume; otherwise a duplicate would be appended after it every run.
        existing_conclusion = next(
            (
                c
                for c in sorted(all_chapters, key=lambda c: c.chapter_number)
                if is_conclusion_title(c.title)
            ),
            None,
        )
        if existing_conclusion is not None:
            conclusion_number = existing_conclusion.chapter_number
        else:
            body_numbers = [c.chapter_number for c in all_chapters if c.chapter_number >= 1]
            conclusion_number = (max(body_numbers) + 1) if body_numbers else 1

        # Reserve the same measured front/back-matter budget used when body
        # chapter targets were allocated; this keeps total manuscript length
        # close to the user-requested total.
        front_matter_target = _front_matter_word_target(
            int(spec_dict.get("target_word_count") or 10000)
        )

        # Introduction = chapter_number 0.
        intro = next((c for c in all_chapters if c.chapter_number == 0), None)
        if intro is None or not intro.content:
            try:
                intro_text = await self._ai(
                    "generate_introduction",
                    spec_dict,
                    summaries,
                    introduction_purpose=blueprint.introduction_purpose or "",
                    target_word_count=front_matter_target,
                    style_guidance=style,
                    temperature=self.temperature,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Introduction generation failed: %s", exc)
                intro_text = ""
            if intro_text and intro_text.strip():
                if intro is None:
                    intro = WritingChapter(
                        book_id=self.wbook.id, chapter_number=0, title="Introduction"
                    )
                    self.session.add(intro)
                intro.title = "Introduction"
                intro.content = intro_text.strip()
                intro.actual_word_count = _wc(intro.content)
                intro.status = "draft"
                intro.target_word_count = front_matter_target
                await self.session.flush()
                await self._snapshot_version(intro, intro.content)

        conclusion = next(
            (c for c in all_chapters if c.chapter_number == conclusion_number), None
        )
        if conclusion is None or not conclusion.content:
            conclusion_purpose = str(
                (self.wbook.generation_state or {}).get("conclusion_purpose", "")
            )
            try:
                conclusion_text = await self._ai(
                    "generate_conclusion",
                    spec_dict,
                    summaries,
                    conclusion_purpose=conclusion_purpose,
                    target_word_count=front_matter_target,
                    style_guidance=style,
                    temperature=self.temperature,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Conclusion generation failed: %s", exc)
                conclusion_text = ""
            if conclusion_text and conclusion_text.strip():
                if conclusion is None:
                    conclusion = WritingChapter(
                        book_id=self.wbook.id,
                        chapter_number=conclusion_number,
                        title="Conclusion",
                    )
                    self.session.add(conclusion)
                conclusion.title = "Conclusion"
                conclusion.content = conclusion_text.strip()
                conclusion.actual_word_count = _wc(conclusion.content)
                conclusion.status = "draft"
                conclusion.target_word_count = front_matter_target
                await self.session.flush()
                await self._snapshot_version(conclusion, conclusion.content)

        await self.session.commit()
        await self.progress(92, "Introduction and conclusion written")

    # ------------------------------------------------------------------
    # stage 8: manuscript assembly + book-level validation
    # ------------------------------------------------------------------
    async def _stage_finalize(self, spec_dict: dict[str, Any]) -> dict[str, Any]:
        await self.progress(94, "Assembling manuscript")
        self.wbook.status = "validating"
        await self._save_state(stage="finalizing")

        result = await self.session.execute(
            select(WritingChapter).where(
                WritingChapter.book_id == self.wbook.id,
                WritingChapter.deleted_at.is_(None),
            ).order_by(WritingChapter.chapter_number)
        )
        chapters = list(result.scalars().all())

        # Assemble the manuscript snapshot.
        from models.book_writing import Manuscript

        parts = [f"# {self.wbook.title}\n"]
        if self.wbook.subtitle:
            parts.append(f"## {self.wbook.subtitle}\n")
        order: list[str] = []
        for ch in chapters:
            if not ch.content:
                continue
            order.append(str(ch.id))
            if ch.chapter_number == 0:
                parts.append("\n\n# Introduction\n\n")
            elif is_conclusion_title(ch.title):
                parts.append("\n\n# Conclusion\n\n")
            else:
                parts.append(f"\n\n# Chapter {ch.chapter_number}: {ch.title}\n\n")
            parts.append(ch.content)
        full_text = "".join(parts)

        ms_result = await self.session.execute(
            select(Manuscript).where(Manuscript.book_id == self.wbook.id)
        )
        manuscript = ms_result.scalar_one_or_none()
        if manuscript is None:
            manuscript = Manuscript(book_id=self.wbook.id)
            self.session.add(manuscript)
        manuscript.full_text = full_text
        manuscript.word_count = _wc(full_text)
        manuscript.chapter_order = order
        manuscript.is_stale = False

        total_words = sum(c.actual_word_count or 0 for c in chapters if c.content)
        self.wbook.actual_word_count = total_words

        # Book-level validation (best-effort).
        await self.progress(96, "Running book-level quality checks")
        summaries = [
            {
                "chapter_number": c.chapter_number,
                "title": c.title,
                "summary": (c.content_summary or c.summary or "")[:300],
                "word_count": c.actual_word_count or 0,
            }
            for c in chapters
            if c.content and c.chapter_number >= 1
        ]
        chapter_validations = [
            {
                "chapter_number": c.chapter_number,
                **(c.validation_result or {}),
            }
            for c in chapters
            if c.validation_result
        ]
        for cv in chapter_validations:
            cv.pop("content", None)
            cv.pop("issues", None)
            cv.pop("missing_sections", None)

        quality: dict[str, Any] = {}
        try:
            quality = await self._ai(
                "validate_manuscript",
                spec_dict,
                summaries,
                total_word_count=total_words,
                chapter_validations=chapter_validations,
                temperature=0.2,
            )
            quality = quality if isinstance(quality, dict) else {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Manuscript validation failed: %s", exc)

        failed_chapters = [
            c.chapter_number for c in chapters if c.status in ("failed", "needs_review")
        ]
        written = [c for c in chapters if c.content]
        # Requests served by the offline fallback are disclosed and can never
        # make a manuscript publication-ready, even when its draft is useful.
        ai_service = getattr(self.engine, "ai", None)
        fallback_units = (
            ai_service.consume_fallback_count(self.wbook.id)
            if ai_service is not None and hasattr(ai_service, "consume_fallback_count")
            else 0
        )
        if fallback_units:
            logger.warning(
                "Book %s: %d generation request(s) served by offline fallback",
                self.wbook.id, fallback_units,
            )

        body_written = [
            c for c in written
            if c.chapter_number >= 1 and not is_conclusion_title(c.title)
        ]
        expected_body_count = int(spec_dict.get("chapter_count") or len(body_written))
        intro_written = any(c.chapter_number == 0 for c in written)
        conclusion_written = any(is_conclusion_title(c.title) for c in written)
        target_words = int(spec_dict.get("target_word_count") or self.wbook.target_word_count or 0)
        minimum_words, maximum_words = _word_count_range(target_words)
        word_count_within_target = minimum_words <= total_words <= maximum_words
        required_scores = {key for key, _threshold in _SCORE_KEYS}
        chapter_validations_complete = bool(body_written) and all(
            c.validation_result
            and not c.validation_result.get("validation_unavailable")
            and all(c.validation_result.get(key) is not None for key in required_scores)
            and c.validation_result.get("passed") is True
            for c in body_written
        )
        manuscript_complete = (
            len(body_written) == expected_body_count and intro_written and conclusion_written
        )
        report = {
            "total_word_count": total_words,
            "target_word_count": target_words,
            "minimum_acceptable_word_count": minimum_words,
            "maximum_acceptable_word_count": maximum_words,
            "word_count_within_target": word_count_within_target,
            "chapter_count": len(body_written),
            "expected_chapter_count": expected_body_count,
            "chapters_written": len(written),
            "introduction_written": intro_written,
            "conclusion_written": conclusion_written,
            "manuscript_complete": manuscript_complete,
            "chapter_validations_complete": chapter_validations_complete,
            "failed_or_review_chapters": failed_chapters,
            "fallback_generated_units": fallback_units,
            "degraded": bool(fallback_units),
            "ai_quality_report": quality,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        self.wbook.quality_report = report

        quality_ready = bool(quality) and quality.get("ready_for_formatting") is True
        ready = (
            quality_ready
            and manuscript_complete
            and chapter_validations_complete
            and word_count_within_target
            and not failed_chapters
            and not fallback_units
        )
        if any(c.status == "failed" for c in chapters):
            self.wbook.status = "revision_required"
            self.wbook.current_step = "writing"
        elif not ready:
            self.wbook.status = "needs_review"
            self.wbook.current_step = "writing"
        else:
            self.wbook.status = "ready_for_formatting"
            self.wbook.current_step = "formatting"

        await self._save_state(stage="complete", progress=100)
        await self.session.commit()

        await self.progress(99, "Book generation complete")
        await self.progress(100, "Generation finished")

        return {
            "writing_book_id": str(self.wbook.id),
            "chapter_count": report["chapter_count"],
            "total_words": total_words,
            "status": self.wbook.status,
            "quality_report": report,
        }


# ---------------------------------------------------------------------------
# Standalone operations (single chapter / validation / status)
# ---------------------------------------------------------------------------
async def _noop_progress(_pct: int, _message: str | None = None) -> None:
    """Progress sink for operations driven outside the job runner."""


async def regenerate_chapter(
    session: AsyncSession,
    engine: BookWritingEngine,
    *,
    user_id: UUID,
    wbook: WritingBook,
    chapter_number: int,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
) -> WritingChapter:
    """Re-run writing + validation + revision for ONE chapter.

    Requires the book to have a specification and blueprint (i.e. full
    generation has run at least once).
    """
    spec = await load_specification(session, wbook.id)
    if spec is None:
        raise LookupError("Book has no specification — run full generation first.")
    spec_dict = spec_to_dict(spec)

    bp_result = await session.execute(
        select(BookBlueprint).where(
            BookBlueprint.book_id == wbook.id, BookBlueprint.deleted_at.is_(None)
        )
    )
    blueprint = bp_result.scalar_one_or_none()
    if blueprint is None or not blueprint.chapters:
        raise LookupError("Book has no blueprint — run full generation first.")

    ch_result = await session.execute(
        select(WritingChapter).where(
            WritingChapter.book_id == wbook.id,
            WritingChapter.chapter_number == chapter_number,
            WritingChapter.deleted_at.is_(None),
        )
    )
    chapter = ch_result.scalar_one_or_none()
    if chapter is None:
        raise LookupError(f"Chapter {chapter_number} not found.")

    pipe = GenerationPipeline(
        session, engine,
        user_id=user_id, wbook=wbook, setup={},
        provider=provider, model=model,
        temperature=temperature, progress=_noop_progress,
    )

    plans = list(blueprint.chapters or [])
    plan = (
        plans[chapter_number - 1]
        if chapter_number - 1 < len(plans)
        else {"title": chapter.title}
    )
    style = await get_style_guidance(session, wbook.id)

    # Continuity: summary of the previous body chapter.
    prev_result = await session.execute(
        select(WritingChapter).where(
            WritingChapter.book_id == wbook.id,
            WritingChapter.chapter_number == chapter_number - 1,
            WritingChapter.deleted_at.is_(None),
        )
    )
    prev = prev_result.scalar_one_or_none()
    prev_summary = (prev.content_summary or prev.summary or "") if prev is not None else ""

    total = len(plans)
    chapter.status = "generating"
    chapter.revision_count = 0
    await session.flush()

    content = await pipe._write_chapter_sections(
        spec_dict, plan, chapter, style, prev_summary, total
    )
    validation = await pipe._validate_and_revise(
        spec_dict, plan, chapter, content, style, prev_summary
    )
    content = validation.pop("content", content)

    chapter.content = content
    chapter.actual_word_count = _wc(content)
    chapter.validation_result = validation
    chapter.content_summary = str(validation.get("summary") or "")[:1500] or chapter.summary
    chapter.status = "draft" if validation.get("passed") else "needs_review"
    await pipe._snapshot_version(chapter, content)
    await session.commit()
    await session.refresh(chapter)
    return chapter


async def validate_book(
    session: AsyncSession,
    engine: BookWritingEngine,
    *,
    user_id: UUID,
    wbook: WritingBook,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Run (or re-run) the book-level quality audit and persist the report."""
    spec = await load_specification(session, wbook.id)
    spec_dict = spec_to_dict(spec) if spec is not None else {
        "book_title": wbook.title,
        "topic": wbook.description or wbook.title,
        "chapter_count": 0,
        "target_word_count": wbook.target_word_count or 0,
    }

    result = await session.execute(
        select(WritingChapter).where(
            WritingChapter.book_id == wbook.id,
            WritingChapter.deleted_at.is_(None),
        ).order_by(WritingChapter.chapter_number)
    )
    chapters = list(result.scalars().all())

    summaries = [
        {
            "chapter_number": c.chapter_number,
            "title": c.title,
            "summary": (c.content_summary or c.summary or "")[:300],
            "word_count": c.actual_word_count or 0,
        }
        for c in chapters
        if c.content and c.chapter_number >= 1
    ]
    total_words = sum(c.actual_word_count or 0 for c in chapters if c.content)

    pipe = GenerationPipeline(
        session, engine,
        user_id=user_id, wbook=wbook, setup={},
        provider=provider, model=model,
        temperature=0.2, progress=_noop_progress,
    )
    quality = await pipe._ai(
        "validate_manuscript",
        spec_dict,
        summaries,
        total_word_count=total_words,
        chapter_validations=[
            {k: v for k, v in (c.validation_result or {}).items()
             if k not in ("content", "issues", "missing_sections")}
            for c in chapters
            if c.validation_result
        ],
        temperature=0.2,
    )
    quality = quality if isinstance(quality, dict) else {}

    failed = [c.chapter_number for c in chapters if c.status in ("failed", "needs_review")]
    report = {
        "total_word_count": total_words,
        "target_word_count": wbook.target_word_count,
        "chapter_count": len([c for c in chapters if c.content and c.chapter_number >= 1]),
        "failed_or_review_chapters": failed,
        "ai_quality_report": quality,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    wbook.quality_report = report
    wbook.actual_word_count = total_words
    await session.commit()
    return report


async def get_generation_status(
    session: AsyncSession, wbook: WritingBook
) -> dict[str, Any]:
    """Snapshot of where generation stands — for the status endpoint."""
    from models.operations import Job

    result = await session.execute(
        select(WritingChapter).where(
            WritingChapter.book_id == wbook.id,
            WritingChapter.deleted_at.is_(None),
        ).order_by(WritingChapter.chapter_number)
    )
    chapters = list(result.scalars().all())

    job: dict[str, Any] | None = None
    if wbook.generation_job_id is not None:
        job_row = await session.get(Job, wbook.generation_job_id)
        if job_row is not None:
            job = {
                "id": str(job_row.id),
                "status": job_row.status,
                "progress": job_row.progress,
                "current_step": job_row.current_step,
                "error_message": job_row.error_message,
            }

    return {
        "book_id": str(wbook.id),
        "status": wbook.status,
        "current_step": wbook.current_step,
        "generation_state": dict(wbook.generation_state or {}),
        "quality_report": wbook.quality_report,
        "job": job,
        "word_counts": {
            "target": wbook.target_word_count,
            "min": wbook.min_word_count,
            "max": wbook.max_word_count,
            "actual": wbook.actual_word_count
            or sum(c.actual_word_count or 0 for c in chapters if c.content),
        },
        "chapters": [
            {
                "chapter_number": c.chapter_number,
                "title": c.title,
                "status": c.status,
                "word_count": c.actual_word_count,
                "target_word_count": c.target_word_count,
                "relevance_score": (c.validation_result or {}).get("relevance_score"),
                "outline_coverage": (c.validation_result or {}).get("outline_coverage"),
                "depth_score": (c.validation_result or {}).get("depth_score"),
                "continuity_score": (c.validation_result or {}).get("continuity_score"),
                "passed": (c.validation_result or {}).get("passed"),
                "revision_count": c.revision_count,
            }
            for c in chapters
        ],
    }
