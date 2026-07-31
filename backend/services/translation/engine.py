"""AI Translation engine — translates book content while preserving structure.

Uses the existing AIService to translate each chapter sequentially, preserving
markdown formatting markers and image placeholders.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError, ValidationAppError
from models.accounts import User
from models.assets import TranslationRecord
from models.book_writing import WritingBook, WritingChapter
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

TRANSLATION_SYSTEM_PROMPT = """You are a professional literary translator. Translate the following text from {source_lang} to {target_lang}.

Rules:
1. Preserve ALL markdown formatting — headers (# ## ###), bold (**), italic (*), lists, etc.
2. Preserve ALL image placeholders and captions — do not translate or modify [IMAGE], ![alt], or {{img}} markers.
3. Maintain the same paragraph structure and line breaks.
4. Preserve the tone, voice, and style of the original.
5. Translate accurately while making the text sound natural in {target_lang}.
6. Return ONLY the translated text — no explanations, no notes, no preambles."""


class TranslationEngine:
    """Translates a full book chapter-by-chapter using AI."""

    def __init__(self, ai_service: AISvc) -> None:
        self._ai = ai_service

    async def translate(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
        source_lang: str,
        target_lang: str,
    ) -> list[WritingChapter]:
        """Translate all chapters of a book and persist translated content."""
        if source_lang not in SUPPORTED_LANGUAGES:
            raise ValidationAppError(f"Source language '{source_lang}' is not supported.")
        if target_lang not in SUPPORTED_LANGUAGES:
            raise ValidationAppError(f"Target language '{target_lang}' is not supported.")
        if source_lang == target_lang:
            raise ValidationAppError("Source and target languages must be different.")

        book = await session.get(WritingBook, book_id)
        if book is None or book.deleted_at is not None:
            raise ResourceNotFoundError("Book not found.")
        if book.user_id != user.id:
            raise ResourceNotFoundError("Book not found.")

        chapters_result = await session.execute(
            select(WritingChapter)
            .where(WritingChapter.book_id == book_id, WritingChapter.deleted_at.is_(None))
            .order_by(WritingChapter.chapter_number),
        )
        chapters = list(chapters_result.scalars())

        if not chapters:
            raise ValidationAppError("Cannot translate a book with no chapters.")

        # Create a translation record.
        record = TranslationRecord(
            book_id=book_id,
            source_language=source_lang,
            target_language=target_lang,
            status=TranslationStatus.RUNNING.value,
        )
        session.add(record)

        source_label = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
        target_label = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        translated_chapters: list[WritingChapter] = []
        try:
            for chapter in chapters:
                content = chapter.content or ""
                if not content.strip():
                    translated_chapters.append(chapter)
                    continue

                # Split into chunks of ~3000 chars for better translation quality.
                chunks = self._split_chunks(content, 3000)
                translated_parts: list[str] = []

                for chunk in chunks:
                    translated = await self._ai.generate_text(
                        system_prompt=TRANSLATION_SYSTEM_PROMPT.format(
                            source_lang=source_label,
                            target_lang=target_label,
                        ),
                        user_prompt=chunk,
                    )
                    translated_parts.append(translated.text)

                chapter.content = "\n\n".join(translated_parts)
                chapter.actual_word_count = len(chapter.content.split())
                translated_chapters.append(chapter)

            record.status = TranslationStatus.COMPLETED.value
        except Exception:
            record.status = TranslationStatus.FAILED.value
            raise

        book.language = target_lang
        await session.commit()

        for ch in translated_chapters:
            await session.refresh(ch)

        return translated_chapters

    async def get_translations(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
    ) -> list[TranslationRecord]:
        """List all translation records for a book."""
        book = await session.get(WritingBook, book_id)
        if book is None or book.user_id != user.id:
            raise ResourceNotFoundError("Book not found.")
        result = await session.execute(
            select(TranslationRecord)
            .where(TranslationRecord.book_id == book_id)
            .order_by(TranslationRecord.created_at.desc()),
        )
        return list(result.scalars())

    @staticmethod
    def supported_languages() -> list[dict[str, str]]:
        """Return all supported language codes and names."""
        return [{"code": code, "name": name} for code, name in SUPPORTED_LANGUAGES.items()]

    @staticmethod
    def _split_chunks(text: str, max_len: int) -> list[str]:
        """Split text into chunks at paragraph boundaries, each under max_len."""
        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for para in paragraphs:
            if current_len + len(para) > max_len and current:
                chunks.append("\n\n".join(current))
                current = [para]
                current_len = len(para)
            else:
                current.append(para)
                current_len += len(para) + 2

        if current:
            chunks.append("\n\n".join(current))
        return chunks


def get_translation_engine(ai_service: AISvc) -> TranslationEngine:
    """Return a translation engine using the provided AI service."""
    return TranslationEngine(ai_service)