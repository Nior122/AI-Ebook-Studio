"""AI translation service for source-preserving translated book editions.

A translated edition is stored separately from its source WritingBook chapters.
Every chapter output is an immutable snapshot linked to its source chapter and
content hash; retries only revisit the selected edition's incomplete chapters.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import ResourceNotFoundError, ValidationAppError
from models.accounts import User
from models.book_writing import (
    TranslatedChapter,
    WritingBook,
    WritingBookTranslation,
    WritingChapter,
)
from models.enums import TranslationStatus
from services.ai_service import AIService as AISvc

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ja": "Japanese",
    "zh": "Chinese (Simplified)",
    "ko": "Korean",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "pl": "Polish",
    "sv": "Swedish",
    "tr": "Turkish",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "uk": "Ukrainian",
}

TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional literary translator. Translate the following text "
    "from {source_lang} to {target_lang}.\n\n"
    "Rules:\n"
    "1. Preserve ALL markdown formatting — headers (# ## ###), bold (**), italic (*), lists, etc.\n"
    "2. Preserve ALL image placeholders and captions — do not translate or modify "
    "[IMAGE], ![alt], or {{img}} markers.\n"
    "3. Maintain the same paragraph structure and line breaks.\n"
    "4. Preserve the tone, voice, and style of the original.\n"
    "5. Translate accurately while making the text sound natural in {target_lang}.\n"
    "6. Return ONLY the translated text — no explanations, notes, or preambles."
)

TranslationProgress = Callable[[int, str | None], Awaitable[None]]


def _language_code(value: str) -> str | None:
    """Normalize a stored language code or display name to its supported code."""
    normalized = value.strip().lower().replace("_", "-")
    if normalized in SUPPORTED_LANGUAGES:
        return normalized
    short_code = normalized.split("-", maxsplit=1)[0]
    if short_code in SUPPORTED_LANGUAGES:
        return short_code
    return next(
        (code for code, name in SUPPORTED_LANGUAGES.items() if name.lower() == normalized),
        None,
    )


def _chapter_hash(chapter: WritingChapter, content: str) -> str:
    """Hash the source text and structural identity for safe resume checks."""
    payload = f"{chapter.id}\0{chapter.chapter_number}\0{chapter.title}\0{content}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _revision_hash(chapters: list[WritingChapter]) -> str:
    """Build a stable hash for the source chapter order and content revision."""
    payload = [
        {
            "id": str(chapter.id),
            "number": chapter.chapter_number,
            "title": chapter.title,
            "content_hash": _chapter_hash(chapter, chapter.content or ""),
        }
        for chapter in chapters
    ]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class TranslationEngine:
    """Translate a WritingBook into a separate, resumable target-language edition."""

    def __init__(self, ai_service: AISvc) -> None:
        self._ai = ai_service

    async def translate(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
        source_lang: str,
        target_lang: str,
        *,
        translation_id: UUID | None = None,
        progress: TranslationProgress | None = None,
    ) -> WritingBookTranslation:
        """Create or resume a translation without modifying source chapters.

        Each chapter result is committed independently so a provider failure
        leaves completed target-language work available for inspection/retry.
        Passing ``translation_id`` resumes only that edition and only while its
        source revision still matches the current manuscript.
        """
        self._validate_language_pair(source_lang, target_lang)

        book_result = await session.execute(
            select(WritingBook).where(
                WritingBook.id == book_id,
                WritingBook.user_id == user.id,
                WritingBook.deleted_at.is_(None),
            )
        )
        book = book_result.scalar_one_or_none()
        if book is None:
            raise ResourceNotFoundError("Book not found.")

        stored_source_language = _language_code(book.language)
        if stored_source_language is None:
            raise ValidationAppError(
                "The manuscript language is not recognized. Update the book language "
                "before translating."
            )
        if stored_source_language != source_lang:
            raise ValidationAppError(
                f"The manuscript is set to {SUPPORTED_LANGUAGES[stored_source_language]}; "
                f"choose that as the source language before translating."
            )

        chapters_result = await session.execute(
            select(WritingChapter)
            .where(
                WritingChapter.book_id == book_id,
                WritingChapter.deleted_at.is_(None),
            )
            .order_by(WritingChapter.chapter_number, WritingChapter.id)
        )
        chapters = list(chapters_result.scalars())
        if not chapters:
            raise ValidationAppError("Cannot translate a book with no chapters.")

        current_revision_hash = _revision_hash(chapters)
        edition: WritingBookTranslation
        if translation_id is None:
            edition = WritingBookTranslation(
                book_id=book.id,
                source_language=source_lang,
                target_language=target_lang,
                source_revision_hash=current_revision_hash,
                source_chapter_count=len(chapters),
                status=TranslationStatus.RUNNING.value,
            )
            session.add(edition)
            await session.flush()
            session.add_all(
                [
                    TranslatedChapter(
                        translation_id=edition.id,
                        source_chapter_id=chapter.id,
                        chapter_number=chapter.chapter_number,
                        title=chapter.title,
                        source_content_hash=_chapter_hash(chapter, chapter.content or ""),
                        status=TranslationStatus.PENDING.value,
                    )
                    for chapter in chapters
                ]
            )
            await session.commit()
        else:
            edition = await self._get_owned_translation(
                session, user, book_id, translation_id, include_chapters=True
            )
            if edition.source_language != source_lang or edition.target_language != target_lang:
                raise ValidationAppError(
                    "The selected translation edition uses a different language pair."
                )
            if edition.status == TranslationStatus.COMPLETED.value:
                return edition
            if edition.source_revision_hash != current_revision_hash:
                raise ValidationAppError(
                    "The source manuscript has changed since this translation started. "
                    "Create a new translated edition to avoid mixing revisions."
                )

            await self._validate_resume_chapters(session, edition, chapters)
            edition.status = TranslationStatus.RUNNING.value
            edition.error_message = None
            edition.completed_at = None
            await session.commit()

        if progress is not None:
            await progress(2, f"Preparing {len(chapters)} chapter(s) for translation")

        source_label = SUPPORTED_LANGUAGES[source_lang]
        target_label = SUPPORTED_LANGUAGES[target_lang]
        translated_rows_result = await session.execute(
            select(TranslatedChapter).where(TranslatedChapter.translation_id == edition.id)
        )
        translated_by_source = {
            row.source_chapter_id: row for row in translated_rows_result.scalars()
        }

        try:
            for index, chapter in enumerate(chapters, start=1):
                translated = translated_by_source[chapter.id]
                if translated.status == TranslationStatus.COMPLETED.value:
                    continue

                source_content = chapter.content or ""
                try:
                    if source_content.strip():
                        chunks = self._split_chunks(source_content, 3000)
                        translated_parts: list[str] = []
                        for chunk in chunks:
                            result = await self._ai.generate_text(
                                system_prompt=TRANSLATION_SYSTEM_PROMPT.format(
                                    source_lang=source_label,
                                    target_lang=target_label,
                                ),
                                user_prompt=chunk,
                            )
                            translated_text = getattr(result, "text", None)
                            if translated_text is None:
                                translated_text = getattr(result, "content", None)
                            if not isinstance(translated_text, str) or not translated_text.strip():
                                raise ValueError("The translation provider returned empty text.")
                            translated_parts.append(translated_text)
                        translated.content = "\n\n".join(translated_parts)
                    else:
                        translated.content = ""

                    translated.word_count = len(translated.content.split())
                    translated.status = TranslationStatus.COMPLETED.value
                    translated.error_message = None
                    edition.translated_chapter_count = sum(
                        row.status == TranslationStatus.COMPLETED.value
                        for row in translated_by_source.values()
                    )
                    edition.target_word_count = sum(
                        row.word_count
                        for row in translated_by_source.values()
                        if row.status == TranslationStatus.COMPLETED.value
                    )
                    await session.commit()
                except Exception as error:
                    translated.status = TranslationStatus.FAILED.value
                    translated.error_message = str(error)[:1000]
                    edition.status = TranslationStatus.FAILED.value
                    edition.error_message = str(error)[:1000]
                    edition.translated_chapter_count = sum(
                        row.status == TranslationStatus.COMPLETED.value
                        for row in translated_by_source.values()
                    )
                    edition.target_word_count = sum(
                        row.word_count
                        for row in translated_by_source.values()
                        if row.status == TranslationStatus.COMPLETED.value
                    )
                    await session.commit()
                    raise

                if progress is not None:
                    pct = 5 + int(90 * index / len(chapters))
                    await progress(pct, f"Translated chapter {index} of {len(chapters)}")

            edition.status = TranslationStatus.COMPLETED.value
            edition.error_message = None
            edition.completed_at = datetime.now(UTC)
            edition.translated_chapter_count = len(chapters)
            edition.target_word_count = sum(row.word_count for row in translated_by_source.values())
            await session.commit()
        except Exception:
            # Chapter-level failures are committed above. This guard covers
            # failures outside an individual provider call while retaining the
            # source and any chapters already translated.
            if edition.status != TranslationStatus.FAILED.value:
                edition.status = TranslationStatus.FAILED.value
                await session.commit()
            raise

        if progress is not None:
            await progress(100, "Translation edition ready")

        return await self._get_owned_translation(
            session, user, book_id, edition.id, include_chapters=True
        )

    async def get_translations(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
    ) -> list[WritingBookTranslation]:
        """List translated editions for a book owned by the caller."""
        await self._get_owned_book(session, user, book_id)
        result = await session.execute(
            select(WritingBookTranslation)
            .where(
                WritingBookTranslation.book_id == book_id,
                WritingBookTranslation.deleted_at.is_(None),
            )
            .order_by(WritingBookTranslation.created_at.desc())
        )
        return list(result.scalars())

    async def get_translation(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
        translation_id: UUID,
    ) -> WritingBookTranslation:
        """Load one translated edition, including its chapter content."""
        return await self._get_owned_translation(
            session, user, book_id, translation_id, include_chapters=True
        )

    async def _get_owned_book(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
    ) -> WritingBook:
        """Return a non-deleted book owned by the caller or conceal its existence."""
        result = await session.execute(
            select(WritingBook).where(
                WritingBook.id == book_id,
                WritingBook.user_id == user.id,
                WritingBook.deleted_at.is_(None),
            )
        )
        book = result.scalar_one_or_none()
        if book is None:
            raise ResourceNotFoundError("Book not found.")
        return book

    async def _get_owned_translation(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
        translation_id: UUID,
        *,
        include_chapters: bool,
    ) -> WritingBookTranslation:
        """Load an edition through its user-owned book relation."""
        await self._get_owned_book(session, user, book_id)
        statement = select(WritingBookTranslation).where(
            WritingBookTranslation.id == translation_id,
            WritingBookTranslation.book_id == book_id,
            WritingBookTranslation.deleted_at.is_(None),
        )
        if include_chapters:
            statement = statement.options(selectinload(WritingBookTranslation.chapters))
        result = await session.execute(statement)
        edition = result.scalar_one_or_none()
        if edition is None:
            raise ResourceNotFoundError("Translation not found.")
        return edition

    async def _validate_resume_chapters(
        self,
        session: AsyncSession,
        edition: WritingBookTranslation,
        source_chapters: list[WritingChapter],
    ) -> None:
        """Ensure the incomplete edition contains the exact same source revision."""
        result = await session.execute(
            select(TranslatedChapter).where(TranslatedChapter.translation_id == edition.id)
        )
        translated_by_source = {row.source_chapter_id: row for row in result.scalars()}
        if len(translated_by_source) != len(source_chapters):
            raise ValidationAppError(
                "The saved translation is incomplete or no longer matches the source chapters. "
                "Create a new translated edition."
            )
        for chapter in source_chapters:
            translated = translated_by_source.get(chapter.id)
            if translated is None or translated.source_content_hash != _chapter_hash(
                chapter, chapter.content or ""
            ):
                raise ValidationAppError(
                    "The source manuscript has changed since this translation started. "
                    "Create a new translated edition to avoid mixing revisions."
                )

    @staticmethod
    def _validate_language_pair(source_lang: str, target_lang: str) -> None:
        """Validate supported source/target codes and reject same-language copies."""
        if source_lang not in SUPPORTED_LANGUAGES:
            raise ValidationAppError(f"Source language '{source_lang}' is not supported.")
        if target_lang not in SUPPORTED_LANGUAGES:
            raise ValidationAppError(f"Target language '{target_lang}' is not supported.")
        if source_lang == target_lang:
            raise ValidationAppError("Source and target languages must be different.")

    @staticmethod
    def supported_languages() -> list[dict[str, str]]:
        """Return all supported language codes and names."""
        return [{"code": code, "name": name} for code, name in SUPPORTED_LANGUAGES.items()]

    @staticmethod
    def _split_chunks(text: str, max_len: int) -> list[str]:
        """Split text at paragraph boundaries, retaining every source character."""
        if max_len < 1:
            raise ValueError("max_len must be greater than zero.")
        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for paragraph in paragraphs:
            if len(paragraph) > max_len:
                if current:
                    chunks.append("\n\n".join(current))
                    current = []
                    current_len = 0
                # Retain oversized paragraphs as a single request rather than
                # splitting inside a word or silently dropping text. Providers
                # that cannot accept it will fail this chapter without touching
                # the source manuscript, and the edition can be resumed.
                chunks.append(paragraph)
                continue

            extra_len = len(paragraph) + (2 if current else 0)
            if current and current_len + extra_len > max_len:
                chunks.append("\n\n".join(current))
                current = [paragraph]
                current_len = len(paragraph)
            else:
                current.append(paragraph)
                current_len += extra_len

        if current:
            chunks.append("\n\n".join(current))
        return chunks


def get_translation_engine(ai_service: AISvc) -> TranslationEngine:
    """Return a translation engine using the provided AI service."""
    return TranslationEngine(ai_service)
