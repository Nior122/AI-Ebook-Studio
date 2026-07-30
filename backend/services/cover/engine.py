"""AI Cover Generator — produces front cover, back cover, and spine descriptions.

Uses the existing AIService to generate cover design prompts that can be fed to
the image generation engine or used with external cover design tools.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError
from models.accounts import User
from models.assets import MarketingAsset
from models.book_writing import WritingBook, WritingChapter
from models.enums import MarketingAssetType
from services.ai_service import AIService as AISvc

COVER_SYSTEM_PROMPT = """You are a professional book cover designer. Create detailed cover design
instructions that a designer or AI image generator can follow to produce a
professional book cover.

For each cover element, provide:
1. Visual concept and composition
2. Color palette (3-5 colors)
3. Typography style
4. Key imagery/illustration elements
5. Mood and atmosphere

Be specific, visual, and actionable."""


class CoverEngine:
    """Generates cover design content for front cover, back cover, and spine."""

    def __init__(self, ai_service: AISvc) -> None:
        self._ai = ai_service

    async def generate_front_cover(self, session: AsyncSession, user: User, book_id: UUID) -> dict:
        book, chapters = await self._load_book(session, user, book_id)
        subject = self._build_subject(book, chapters)

        prompt = f"""{subject}

Design the FRONT COVER for this book:
- Create a compelling visual that captures the book's core message
- Include title placement: "{book.title}"
- Include subtitle placement: "{book.subtitle or ''}"
- Include author name: "{book.author_name or 'Author'}"

Return a detailed cover design brief with:
1. Overall concept (2-3 sentences)
2. Color palette (3-5 specific colors)
3. Typography style
4. Key visual elements
5. Layout description"""

        result = await self._ai.generate_text(
            system_prompt=COVER_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
        return {"content": result.text, "type": "front_cover"}

    async def generate_back_cover(self, session: AsyncSession, user: User, book_id: UUID) -> dict:
        book, chapters = await self._load_book(session, user, book_id)
        description = book.description or ""
        if chapters:
            snippet = chapters[0].content[:300] if chapters[0].content else ""
        else:
            snippet = ""

        prompt = f"""Book Title: {book.title}
Description: {description}
First chapter excerpt: {snippet}

Design the BACK COVER for this book:
1. Book description / blurb (100-150 words)
2. Author bio (50-75 words)
3. Back cover layout description
4. Barcode/ISBN placeholder position"""

        result = await self._ai.generate_text(
            system_prompt=COVER_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
        return {"content": result.text, "type": "back_cover"}

    async def generate_spine(self, session: AsyncSession, user: User, book_id: UUID) -> dict:
        book, chapters = await self._load_book(session, user, book_id)
        prompt = f"""Book Title: {book.title}
Author: {book.author_name or 'Author'}
Estimated page count: {sum(len((c.content or '').split()) // 300 + 1 for c in chapters) if chapters else 200}

Design the SPINE for this book:
1. Text layout (title, author name orientation)
2. Minimum spine width recommendation
3. Publisher logo placement
4. Color and texture"""

        result = await self._ai.generate_text(
            system_prompt=COVER_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
        return {"content": result.text, "type": "spine"}

    async def generate_all(self, session: AsyncSession, user: User, book_id: UUID) -> dict[str, object]:
        """Generate all cover components (front, back, spine)."""
        front = await self.generate_front_cover(session, user, book_id)
        back = await self.generate_back_cover(session, user, book_id)
        spine = await self.generate_spine(session, user, book_id)
        return {"front": front, "back": back, "spine": spine}

    async def _load_book(self, session: AsyncSession, user: User, book_id: UUID):
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
        return book, chapters

    def _build_subject(self, book: WritingBook, chapters: list[WritingChapter]) -> str:
        parts = [f"Book Title: {book.title}"]
        if book.subtitle:
            parts.append(f"Subtitle: {book.subtitle}")
        if book.description:
            parts.append(f"Description: {book.description}")
        if book.target_audience:
            parts.append(f"Target Audience: {book.target_audience}")
        if chapters:
            parts.append(f"Chapters: {len(chapters)}")
            parts.append("Chapter titles: " + ", ".join(c.title for c in chapters[:5]))
        if book.language:
            parts.append(f"Language: {book.language}")
        if book.tone:
            parts.append(f"Tone: {book.tone}")
        return "\n".join(parts)


def get_cover_engine(ai_service: AISvc) -> CoverEngine:
    return CoverEngine(ai_service)