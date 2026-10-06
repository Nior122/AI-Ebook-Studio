"""Regression coverage for source-preserving translated editions."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from models.accounts import User
from models.book_writing import TranslatedChapter, WritingBook, WritingChapter
from services.ai_service import get_ai_service
from services.translation.engine import TranslationEngine


class PrefixTranslationAI:
    """Small deterministic translator used without external credentials."""

    def __init__(self, fail_on_call: int | None = None) -> None:
        self.calls: list[str] = []
        self.fail_on_call = fail_on_call

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        **_: Any,
    ) -> SimpleNamespace:
        self.calls.append(user_prompt)
        if self.fail_on_call == len(self.calls):
            raise RuntimeError("simulated provider interruption")
        return SimpleNamespace(text=f"[ES] {user_prompt}")


async def register(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Translator"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_translation_api_creates_a_separate_edition(client: AsyncClient) -> None:
    """A successful HTTP translation leaves the source content and language intact."""
    ai = PrefixTranslationAI()
    app.dependency_overrides[get_ai_service] = lambda: ai
    try:
        headers = await register(client, "translation-source@example.com")
        created = await client.post(
            "/api/v1/book-writing/books",
            json={
                "title": "A Teacher's Guide to AI",
                "description": "Practical classroom workflows.",
                "language": "en",
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        book_id = created.json()["id"]

        chapter = await client.post(
            f"/api/v1/book-writing/books/{book_id}/chapters",
            json={"title": "Lesson Planning", "chapter_number": 1},
            headers=headers,
        )
        assert chapter.status_code == 201, chapter.text
        chapter_id = chapter.json()["id"]
        source = "# Lesson Planning\n\nUse AI to draft a lesson, then verify the facts."
        updated = await client.patch(
            f"/api/v1/book-writing/chapters/{chapter_id}",
            json={"payload": {"content": source}},
            headers=headers,
        )
        assert updated.status_code == 200, updated.text

        translated = await client.post(
            f"/api/v1/book-writing/books/{book_id}/translate",
            json={"source_language": "en", "target_language": "es"},
            headers=headers,
        )
        assert translated.status_code == 200, translated.text
        edition = translated.json()
        assert edition["status"] == "COMPLETED"
        assert edition["source_chapter_count"] == 1
        assert edition["translated_chapter_count"] == 1
        assert edition["chapters"][0]["source_chapter_id"] == chapter_id
        assert edition["chapters"][0]["content"] == f"[ES] {source}"

        source_chapters = await client.get(
            f"/api/v1/book-writing/books/{book_id}/chapters", headers=headers
        )
        assert source_chapters.status_code == 200
        assert source_chapters.json()[0]["content"] == source
        book = await client.get(f"/api/v1/book-writing/books/{book_id}", headers=headers)
        assert book.json()["language"] == "en"

        history = await client.get(
            f"/api/v1/book-writing/books/{book_id}/translate/history", headers=headers
        )
        assert history.status_code == 200
        assert history.json()["items"][0]["id"] == edition["id"]
        reopened = await client.get(
            f"/api/v1/book-writing/books/{book_id}/translate/{edition['id']}",
            headers=headers,
        )
        assert reopened.status_code == 200
        assert reopened.json()["chapters"][0]["content"] == f"[ES] {source}"

        other_headers = await register(client, "translation-other@example.com")
        forbidden = await client.get(
            f"/api/v1/book-writing/books/{book_id}/translate/{edition['id']}",
            headers=other_headers,
        )
        assert forbidden.status_code == 404
    finally:
        app.dependency_overrides.pop(get_ai_service, None)


@pytest.mark.asyncio
async def test_failed_translation_can_resume_without_changing_source(
    db_session: AsyncSession,
) -> None:
    """A partial target edition can resume from its last completed chapter."""
    user = User(email="translation-resume@example.com", status="active")
    db_session.add(user)
    await db_session.flush()

    book = WritingBook(user_id=user.id, title="Safe Translation", language="en")
    db_session.add(book)
    await db_session.flush()

    source_texts = ["First original chapter.", "Second original chapter."]
    chapters = [
        WritingChapter(
            book_id=book.id,
            chapter_number=index,
            title=f"Chapter {index}",
            content=content,
            actual_word_count=len(content.split()),
        )
        for index, content in enumerate(source_texts, start=1)
    ]
    db_session.add_all(chapters)
    await db_session.commit()

    failing_ai = PrefixTranslationAI(fail_on_call=2)
    engine = TranslationEngine(failing_ai)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="simulated provider interruption"):
        await engine.translate(db_session, user, book.id, "en", "es")

    persisted_source = await db_session.execute(
        select(WritingChapter)
        .where(WritingChapter.book_id == book.id)
        .order_by(WritingChapter.chapter_number)
    )
    assert [chapter.content for chapter in persisted_source.scalars()] == source_texts

    records = await engine.get_translations(db_session, user, book.id)
    assert len(records) == 1
    record = records[0]
    assert record.status == "FAILED"
    assert record.translated_chapter_count == 1

    partial = await db_session.execute(
        select(TranslatedChapter)
        .where(TranslatedChapter.translation_id == record.id)
        .order_by(TranslatedChapter.chapter_number)
    )
    partial_rows = list(partial.scalars())
    assert [row.status for row in partial_rows] == ["COMPLETED", "FAILED"]
    assert partial_rows[0].content == f"[ES] {source_texts[0]}"

    retry_ai = PrefixTranslationAI()
    resumed = await TranslationEngine(retry_ai).translate(
        db_session,
        user,
        book.id,
        "en",
        "es",
        translation_id=record.id,
    )
    assert resumed.id == record.id
    assert resumed.status == "COMPLETED"
    assert resumed.translated_chapter_count == 2
    assert retry_ai.calls == [source_texts[1]]

    persisted_source = await db_session.execute(
        select(WritingChapter)
        .where(WritingChapter.book_id == book.id)
        .order_by(WritingChapter.chapter_number)
    )
    assert [chapter.content for chapter in persisted_source.scalars()] == source_texts
    translated_rows = await db_session.execute(
        select(TranslatedChapter)
        .where(TranslatedChapter.translation_id == record.id)
        .order_by(TranslatedChapter.chapter_number)
    )
    assert [row.content for row in translated_rows.scalars()] == [
        f"[ES] {source_texts[0]}",
        f"[ES] {source_texts[1]}",
    ]


@pytest.mark.asyncio
async def test_translation_resume_rejects_changed_source(db_session: AsyncSession) -> None:
    """A retry cannot mix old translated chapters with a changed source revision."""
    user = User(email="translation-drift@example.com", status="active")
    db_session.add(user)
    await db_session.flush()
    book = WritingBook(user_id=user.id, title="Source Revision", language="en")
    db_session.add(book)
    await db_session.flush()
    chapter = WritingChapter(
        book_id=book.id,
        chapter_number=1,
        title="Original",
        content="Original text.",
        actual_word_count=2,
    )
    db_session.add(chapter)
    await db_session.commit()

    first_ai = PrefixTranslationAI(fail_on_call=1)
    engine = TranslationEngine(first_ai)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        await engine.translate(db_session, user, book.id, "en", "es")
    record = (await engine.get_translations(db_session, user, book.id))[0]

    chapter.content = "User-edited source text."
    await db_session.commit()
    with pytest.raises(Exception, match="source manuscript has changed"):
        await TranslationEngine(PrefixTranslationAI()).translate(
            db_session,
            user,
            book.id,
            "en",
            "es",
            translation_id=record.id,
        )


@pytest.mark.asyncio
async def test_async_translation_handler_uses_separate_edition(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The background route shares the safe engine and never edits the source."""
    from services import ai_service
    from services.jobs.handlers import _translation_handler

    user = User(email="translation-job@example.com", status="active")
    db_session.add(user)
    await db_session.flush()
    book = WritingBook(user_id=user.id, title="Async Translation", language="en")
    db_session.add(book)
    await db_session.flush()
    source = "A source chapter for the queued translation."
    chapter = WritingChapter(
        book_id=book.id,
        chapter_number=1,
        title="Async Chapter",
        content=source,
        actual_word_count=len(source.split()),
    )
    db_session.add(chapter)
    await db_session.commit()

    fake_ai = PrefixTranslationAI()
    monkeypatch.setattr(ai_service, "AIService", lambda: fake_ai)
    progress_events: list[tuple[int, str | None]] = []

    async def progress(percent: int, step: str | None = None) -> None:
        progress_events.append((percent, step))

    result = await _translation_handler(
        db_session,
        uuid4(),
        {
            "user_id": str(user.id),
            "book_id": str(book.id),
            "source_lang": "en",
            "target_lang": "es",
        },
        progress,
    )

    await db_session.refresh(chapter)
    assert chapter.content == source
    assert result is not None
    assert result["status"] == "COMPLETED"
    assert result["translation_id"]
    assert progress_events[-1] == (100, "Translation edition ready")
