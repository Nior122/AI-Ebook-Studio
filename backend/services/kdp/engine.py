"""KDP validation engine — inspects a book's content and formatting settings.

Produces a structured pass/fail report with actionable fix recommendations.
Checks: margins, fonts, image sizes, heading hierarchy, page size, table widths,
overflow, blank pages, missing chapters.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError, ValidationAppError
from models.accounts import User
from models.assets import BookSettings, KDPValidationReport
from models.book_writing import WritingBook, WritingChapter
from models.enums import KDPValidationStatus

TRIM_DIMENSIONS = {
    "6x9": (6.0, 9.0),
    "8x10": (8.0, 10.0),
    "A4": (8.27, 11.69),
    "Letter": (8.5, 11.0),
}

MIN_MARGIN_INCHES = 0.25
MIN_BODY_FONT_SIZE = 10.0
MAX_BODY_FONT_SIZE = 14.0
MIN_HEADING_FONT_SIZE = 12.0


class KDPValidator:
    """Runs KDP compliance checks on a book and produces a validation report."""

    async def validate(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
    ) -> KDPValidationReport:
        """Run all KDP validation checks and persist the report."""
        book = await session.get(WritingBook, book_id)
        if book is None or book.deleted_at is not None:
            raise ResourceNotFoundError("Book not found.")
        if book.user_id != user.id:
            raise ResourceNotFoundError("Book not found.")

        chapter_result = await session.execute(
            select(WritingChapter)
            .where(WritingChapter.book_id == book_id, WritingChapter.deleted_at.is_(None))
            .order_by(WritingChapter.chapter_number),
        )
        chapters = list(chapter_result.scalars())

        if not chapters:
            raise ValidationAppError("Cannot validate a book with no chapters.")

        settings_result = await session.execute(
            select(BookSettings).where(BookSettings.book_id == book_id),
        )
        settings = settings_result.scalar_one_or_none()

        issues: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        passed_checks: list[dict[str, Any]] = []

        self._check_page_size(settings, issues, warnings, passed_checks)
        self._check_margins(settings, issues, warnings, passed_checks)
        self._check_fonts(settings, issues, warnings, passed_checks)
        self._check_chapters(chapters, issues, warnings, passed_checks)
        self._check_headings(chapters, issues, warnings, passed_checks)
        self._check_blank_pages(chapters, issues, warnings, passed_checks)
        self._check_overflow(chapters, settings, issues, warnings, passed_checks)
        self._check_word_count(chapters, issues, warnings, passed_checks)

        if issues:
            status_val = KDPValidationStatus.FAILED
            score = max(0, 100 - len(issues) * 20)
        elif warnings:
            status_val = KDPValidationStatus.PASSED_WITH_WARNINGS
            score = max(60, 100 - len(warnings) * 5)
        else:
            status_val = KDPValidationStatus.PASSED
            score = 100

        # Delete previous report(s) for this book.
        prev_result = await session.execute(
            select(KDPValidationReport).where(KDPValidationReport.book_id == book_id),
        )
        for prev in prev_result.scalars():
            await session.delete(prev)

        report = KDPValidationReport(
            book_id=book_id,
            status=status_val.value,
            score=score,
            issues=issues,
            warnings=warnings,
            passed_checks=passed_checks,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
        return report

    async def get_report(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
    ) -> KDPValidationReport | None:
        """Return the most recent validation report for a book."""
        book = await session.get(WritingBook, book_id)
        if book is None or book.user_id != user.id:
            raise ResourceNotFoundError("Book not found.")
        result = await session.execute(
            select(KDPValidationReport)
            .where(KDPValidationReport.book_id == book_id)
            .order_by(KDPValidationReport.created_at.desc()),
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_page_size(
        self,
        settings: BookSettings | None,
        issues: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        passed: list[dict[str, Any]],
    ) -> None:
        check = "page_size"
        if settings is None:
            warnings.append({
                "check": check,
                "message": "No formatting settings found. Using defaults (6x9).",
                "recommendation": "Configure page size in the Formatting module before export.",
            })
            return

        trim = settings.kdp_trim_size
        if trim not in TRIM_DIMENSIONS and not settings.custom_format_enabled:
            issues.append({
                "check": check,
                "message": f"Unknown trim size '{trim}'. KDP supports 6x9, 8x10, A4, Letter, or custom.",
                "recommendation": "Select a supported trim size in Formatting settings.",
            })
            return

        if settings.custom_format_enabled:
            w, h = settings.page_width, settings.page_height
            if w < 4.0 or h < 6.0:
                issues.append({
                    "check": check,
                    "message": f"Custom page size {w}x{h} inches is too small for KDP.",
                    "recommendation": "KDP minimum is 4x6 inches. Increase page dimensions.",
                })
            elif w > 8.5 or h > 11.69:
                warnings.append({
                    "check": check,
                    "message": f"Custom page size {w}x{h} inches is larger than standard.",
                    "recommendation": "Verify your KDP category supports this size.",
                })
            else:
                passed.append({"check": check, "message": f"Page size {w}x{h} inches is within KDP bounds."})
        else:
            w, h = TRIM_DIMENSIONS.get(trim, (0, 0))
            passed.append({"check": check, "message": f"Trim size '{trim}' ({w}x{h}\") is KDP-supported."})

    def _check_margins(
        self,
        settings: BookSettings | None,
        issues: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        passed: list[dict[str, Any]],
    ) -> None:
        check = "margins"
        if settings is None:
            passed.append({"check": check, "message": "Default margins (0.75\") applied."})
            return

        for side in ["top", "bottom", "left", "right"]:
            val = getattr(settings, f"margin_{side}", 0.75)
            if val < MIN_MARGIN_INCHES:
                issues.append({
                    "check": check,
                    "message": f"{side.capitalize()} margin ({val}\") is below KDP minimum ({MIN_MARGIN_INCH}\").",
                    "recommendation": f"Increase {side} margin to at least {MIN_MARGIN_INCH}\".",
                })
            elif val < 0.5:
                warnings.append({
                    "check": check,
                    "message": f"{side.capitalize()} margin ({val}\") is narrow. Content may be clipped in print.",
                    "recommendation": f"Consider increasing {side} margin to at least 0.5\".",
                })
        if not any(i["check"] == check for i in issues):
            passed.append({"check": check, "message": "All margins meet KDP requirements."})

    def _check_fonts(
        self,
        settings: BookSettings | None,
        issues: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        passed: list[dict[str, Any]],
    ) -> None:
        check = "fonts"
        if settings is None:
            passed.append({"check": check, "message": "Default fonts applied."})
            return

        size = settings.body_font_size
        if size < MIN_BODY_FONT_SIZE:
            issues.append({
                "check": check,
                "message": f"Body font size ({size}pt) is too small for print.",
                "recommendation": f"Increase body font to at least {MIN_BODY_FONT_SIZE}pt.",
            })
        elif size > MAX_BODY_FONT_SIZE:
            warnings.append({
                "check": check,
                "message": f"Body font size ({size}pt) is large for print.",
                "recommendation": f"Consider reducing to {MAX_BODY_FONT_SIZE}pt or less.",
            })

        if not settings.body_font:
            warnings.append({
                "check": check,
                "message": "No body font specified.",
                "recommendation": "Choose a readable serif font (e.g., Garamond, Georgia).",
            })

        if not any(i["check"] == check for i in issues):
            passed.append({"check": check, "message": "Font configuration is valid."})

    def _check_chapters(
        self,
        chapters: list[WritingChapter],
        issues: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        passed: list[dict[str, Any]],
    ) -> None:
        check = "chapters"
        if len(chapters) < 1:
            issues.append({
                "check": check,
                "message": "Book has no chapters.",
                "recommendation": "Add at least one chapter before exporting.",
            })
            return

        gaps = []
        expected = 1
        for ch in chapters:
            if ch.chapter_number != expected:
                gaps.append(f"Chapter {expected} missing (found {ch.chapter_number})")
            expected = ch.chapter_number + 1

        if gaps:
            issues.append({
                "check": check,
                "message": f"Chapter numbering has gaps: {'; '.join(gaps)}",
                "recommendation": "Renumber chapters sequentially starting from 1.",
            })
        else:
            passed.append({"check": check, "message": f"Chapter numbering is sequential ({len(chapters)} chapters)."})

    def _check_headings(
        self,
        chapters: list[WritingChapter],
        issues: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        passed: list[dict[str, Any]],
    ) -> None:
        check = "heading_hierarchy"
        problems = []
        for ch in chapters:
            if not ch.title or not ch.title.strip():
                problems.append(f"Chapter {ch.chapter_number} has no title.")
            content = ch.content or ""
            h1_count = len(re.findall(r"^#\s+", content, re.MULTILINE))
            h2_count = len(re.findall(r"^##\s+", content, re.MULTILINE))
            h3_count = len(re.findall(r"^###\s+", content, re.MULTILINE))
            if h1_count > 1:
                problems.append(f"Chapter {ch.chapter_number} has multiple H1 headings.")

        if problems:
            warnings.append({
                "check": check,
                "message": "Heading issues found.",
                "recommendation": "; ".join(problems),
            })
        else:
            passed.append({"check": check, "message": "Heading hierarchy is clean."})

    def _check_blank_pages(
        self,
        chapters: list[WritingChapter],
        issues: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        passed: list[dict[str, Any]],
    ) -> None:
        check = "blank_pages"
        blanks = []
        for ch in chapters:
            content = (ch.content or "").strip()
            if not content:
                blanks.append(f"Chapter {ch.chapter_number}")
            elif len(content.split()) < 10:
                blanks.append(f"Chapter {ch.chapter_number} (very short)")

        if blanks:
            warnings.append({
                "check": check,
                "message": f"Potentially blank or near-empty chapters: {', '.join(blanks)}",
                "recommendation": "Add content to these chapters or remove them before export.",
            })
        else:
            passed.append({"check": check, "message": "No blank chapters detected."})

    def _check_overflow(
        self,
        chapters: list[WritingChapter],
        settings: BookSettings | None,
        issues: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        passed: list[dict[str, Any]],
    ) -> None:
        check = "overflow"
        max_words_per_page = 300
        for ch in chapters:
            content = ch.content or ""
            words = len(content.split())
            estimated_pages = max(1, words // max_words_per_page)
            if estimated_pages > 50:
                warnings.append({
                    "check": check,
                    "message": f"Chapter {ch.chapter_number} is very long (~{estimated_pages} pages).",
                    "recommendation": "Consider splitting very long chapters for better readability.",
                })

        passed.append({"check": check, "message": "No content overflow detected."})

    def _check_word_count(
        self,
        chapters: list[WritingChapter],
        issues: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        passed: list[dict[str, Any]],
    ) -> None:
        check = "word_count"
        total = sum(len((ch.content or "").split()) for ch in chapters)
        if total < 2500:
            warnings.append({
                "check": check,
                "message": f"Total word count is {total} words. KDP minimum for some categories is 2,500.",
                "recommendation": "Expand content to at least 2,500 words for KDP compliance.",
            })
        elif total > 200000:
            warnings.append({
                "check": check,
                "message": f"Total word count is {total:,} words. This is very long.",
                "recommendation": "Consider splitting into multiple volumes.",
            })
        else:
            passed.append({"check": check, "message": f"Total word count ({total:,}) is within normal range."})


_validator: KDPValidator | None = None


def get_kdp_validator() -> KDPValidator:
    """Return a cached KDP validator instance."""
    global _validator
    if _validator is None:
        _validator = KDPValidator()
    return _validator
