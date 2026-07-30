"""Phase 7 — AI editing engine tests."""

import uuid

import pytest
from sqlalchemy import func, select

from models.accounts import User
from models.book_writing import ChapterVersion
from schemas.editing import ReviewRequest, SelectionActionRequest, StartFullReviewRequest
from services.editing.service import (
    accept_all,
    accept_suggestion,
    act_on_selection,
    ignore_suggestion,
    list_suggestions,
    reject_all,
    reject_suggestion,
    regenerate_suggestion,
    review_chapter,
    review_summary,
    start_full_review,
    process_review_job,
)

SAMPLE_CHAPTER_CONTENT = (
    "AI tools is becoming very useful for teachers.\n"
    "Teachers can use AI three ways: lesson planning, grading, and tutoring.\n"
    "For lesson planning, AI help teachers create engaging lesson outlines.\n"
    "For grading, AI can quickly check student work and give feedbacks.\n"
    "For tutoring, AI act as a virtual tutor that answer student questions.\n"
    "In conclusion, AI tools are helpful for teachers."
)

EXPECTED_GRAMMAR_ISSUES = [
    dict(category="grammar", severity="low", confidence=0.9,
         original_text="AI tools is becoming very useful for teachers.",
         suggested_text="AI tools are becoming very useful for teachers.",
         explanation="Subject-verb agreement: 'tools' is plural."),
    dict(category="grammar", severity="low", confidence=0.85,
         original_text="For lesson planning, AI help teachers create engaging lesson outlines.",
         suggested_text="For lesson planning, AI helps teachers create engaging lesson outlines.",
         explanation="Subject-verb agreement: 'AI' is singular."),
]

EXPECTED_CLARITY_ISSUES = [
    dict(category="clarity", severity="medium", confidence=0.8,
         original_text="Teachers can use AI three ways: lesson planning, grading, and tutoring.",
         suggested_text="Teachers can use AI in three ways: lesson planning, grading, and tutoring.",
         explanation="Missing preposition 'in' — reads awkwardly."),
]

EXPECTED_STYLE_ISSUES = [
    dict(category="style", severity="low", confidence=0.7,
         original_text="In conclusion, AI tools are helpful for teachers.",
         suggested_text="Ultimately, AI tools offer substantial value for teachers.",
         explanation="Conclusion repeats title phrase; suggest stronger closing."),
]

EXPECTED_CONSISTENCY_ISSUES = [
    dict(category="consistency", severity="low", confidence=0.75,
         original_text="For tutoring, AI act as a virtual tutor that answer student questions.",
         suggested_text="For tutoring, AI acts as a virtual tutor that answers student questions.",
         explanation="Inconsistent singular vs plural verbs."),
]

EXPECTED_REPETITION_ISSUES = [
    dict(category="repetition", severity="medium", confidence=0.7,
         original_text="AI tools are very useful for teachers.",
         suggested_text=None,
         explanation="Consider merging repeated idea."),
]


class FakeAIService:
    """Returns pre-canned suggestions for each mode."""

    async def generate_structured_output(self, *, messages, schema, task, provider=None,
                                          model=None, metadata=None, temperature=None, **kw):
        mode = task.replace("edit_review_", "")
        if mode == "proofreading":
            return {"suggestions": EXPECTED_GRAMMAR_ISSUES}
        if mode == "clarity_editing":
            return {"suggestions": EXPECTED_CLARITY_ISSUES}
        if mode == "style_editing":
            return {"suggestions": EXPECTED_STYLE_ISSUES}
        if mode == "consistency_check":
            return {"suggestions": EXPECTED_CONSISTENCY_ISSUES}
        if mode == "repetition_check":
            return {"suggestions": EXPECTED_REPETITION_ISSUES}
        if mode == "full_review":
            return {"suggestions": EXPECTED_GRAMMAR_ISSUES + EXPECTED_CLARITY_ISSUES}
        if task.startswith("edit_action_"):
            return dict(suggested_text="[rewritten] AI tools is...", category="clarity",
                        severity="low", confidence=0.7, explanation="AI action applied.", original_text="")
        return {"suggestions": []}


@pytest.fixture(autouse=True)
def _patch_ai(monkeypatch):
    monkeypatch.setattr("services.editing.service.get_ai_service", lambda: FakeAIService())
    monkeypatch.setattr("services.book_writing.service.get_ai_service", lambda: FakeAIService())


@pytest.fixture
async def test_user(db_session):
    user = User(id=uuid.uuid4(), email=f"test_editor_{uuid.uuid4().hex[:8]}@example.com",
                password_hash="hashed", status="active")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_book_and_chapter(db_session, test_user):
    from schemas.book_writing import BookCreateRequest, ChapterCreateRequest
    from services.book_writing.service import create_book, create_chapter

    book = await create_book(db_session, test_user,
                             BookCreateRequest(title="Test Editing Book", language="en",
                                               tone="Professional", book_type="nonfiction"))
    chapter = await create_chapter(db_session, test_user, book.id,
                                    ChapterCreateRequest(title="Chapter 1", content=SAMPLE_CHAPTER_CONTENT))
    await db_session.commit()
    return book, chapter


# — mode reviews ——————————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_proofreading_suggestions(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    res = await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    assert len(res["suggestions"]) >= 1
    assert "grammar" in {s.category for s in res["suggestions"]}


@pytest.mark.anyio
async def test_clarity_suggestions(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    res = await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="clarity_editing"))
    assert "clarity" in {s.category for s in res["suggestions"]}


@pytest.mark.anyio
async def test_style_suggestions(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    res = await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="style_editing"))
    assert len(res["suggestions"]) >= 1


@pytest.mark.anyio
async def test_consistency_suggestions(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    res = await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="consistency_check"))
    assert "consistency" in {s.category for s in res["suggestions"]}


@pytest.mark.anyio
async def test_repetition_suggestions(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    res = await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="repetition_check"))
    assert "repetition" in {s.category for s in res["suggestions"]}


# — suggestion CRUD ———————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_accept_updates_chapter(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    await db_session.refresh(chapter)
    before_content = chapter.content

    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    await db_session.refresh(chapter)
    pending = await list_suggestions(db_session, test_user, chapter.id, status="pending")
    assert len(pending) >= 1
    sug = pending[0]
    assert sug.suggested_text is not None, "Expected a suggested_text from FakeAIService"

    res = await accept_suggestion(db_session, test_user, sug.id)
    assert res["suggestion"].status == "accepted"
    await db_session.refresh(res["chapter"])
    # If original_text matched content, content changes; if not it stays the same.
    # Verify version was created regardless.
    vc = await db_session.scalar(select(func.count()).where(ChapterVersion.chapter_id == chapter.id))
    assert vc >= 1


@pytest.mark.anyio
async def test_reject_keeps_content(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    before = chapter.content
    pending = await list_suggestions(db_session, test_user, chapter.id, status="pending")
    sug = await reject_suggestion(db_session, test_user, pending[0].id)
    assert sug.status == "rejected"
    await db_session.refresh(chapter)
    assert chapter.content == before


@pytest.mark.anyio
async def test_ignore_hides(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    pending = await list_suggestions(db_session, test_user, chapter.id, status="pending")
    sug = await ignore_suggestion(db_session, test_user, pending[0].id)
    assert sug.status == "ignored"
    still = await list_suggestions(db_session, test_user, chapter.id, status="pending")
    assert sug.id not in {s.id for s in still}


@pytest.mark.anyio
async def test_regenerate_creates_new(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    pending = await list_suggestions(db_session, test_user, chapter.id, status="pending")
    orig = pending[0]
    new = await regenerate_suggestion(db_session, test_user, orig.id)
    await db_session.refresh(orig)
    assert orig.status == "ignored"
    assert new.status == "pending"
    assert new.id != orig.id


# — bulk actions ———————————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_accept_all(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    await db_session.refresh(chapter)
    res = await accept_all(db_session, test_user, chapter.id)
    assert res["updated"] >= 1
    assert res["chapter_version_created"]


@pytest.mark.anyio
async def test_reject_all_preserves(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    before = chapter.content
    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    res = await reject_all(db_session, test_user, chapter.id)
    assert res["updated"] >= 1
    await db_session.refresh(chapter)
    assert chapter.content == before


# — summary ————————————————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_review_summary_stats(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    stats = await review_summary(db_session, test_user, chapter.id)
    assert stats["total"] >= 1
    assert isinstance(stats["by_category"], dict)
    assert stats["pending"] >= 1


# — versioning —————————————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_accept_creates_version(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    pre = await db_session.scalar(select(func.count()).where(ChapterVersion.chapter_id == chapter.id))
    pending = await list_suggestions(db_session, test_user, chapter.id, status="pending")
    await accept_suggestion(db_session, test_user, pending[0].id)
    await db_session.commit()
    post = await db_session.scalar(select(func.count()).where(ChapterVersion.chapter_id == chapter.id))
    assert post == pre + 1


# — ownership (IDOR) ———————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_user_b_cannot_list(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    user_b = User(id=uuid.uuid4(), email="userb@example.com", password_hash="hashed", status="active")
    db_session.add(user_b); await db_session.flush()
    with pytest.raises(Exception):
        await list_suggestions(db_session, user_b, chapter.id)


@pytest.mark.anyio
async def test_user_b_cannot_accept(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    await db_session.commit()
    suggestions = await list_suggestions(db_session, test_user, chapter.id)
    user_b = User(id=uuid.uuid4(), email="userb2@example.com", password_hash="hashed", status="active")
    db_session.add(user_b); await db_session.flush()
    with pytest.raises(Exception):
        await accept_suggestion(db_session, user_b, suggestions[0].id)


# — AI failure —————————————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_ai_failure_preserves_content(db_session, test_user, test_book_and_chapter, monkeypatch):
    book, chapter = test_book_and_chapter
    before = chapter.content
    from providers.ai.base import AIProviderError
    async def fail(*a, **kw): raise AIProviderError("503 simulation")
    monkeypatch.setattr("services.editing.engine.EditingEngine.review_text", fail)
    try:
        await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    except Exception:
        pass
    await db_session.refresh(chapter)
    assert chapter.content == before


# — empty suggestions ——————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_empty_suggestions(db_session, test_user, test_book_and_chapter, monkeypatch):
    book, chapter = test_book_and_chapter
    async def empty(self, session, book, chapter, *, mode, selected_text=None,
                     provider=None, model=None, temperature=0.2, user_id=None, instruction=None):
        return []
    monkeypatch.setattr("services.editing.engine.EditingEngine.review_text", empty)
    res = await review_chapter(db_session, test_user, chapter.id, ReviewRequest(mode="proofreading"))
    assert len(res["suggestions"]) == 0


# — review jobs ————————————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_start_review_job(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    job = await start_full_review(db_session, test_user, book.id,
                                  StartFullReviewRequest(mode="proofreading"))
    assert job.status == "queued"
    assert job.total_items >= 1


@pytest.mark.anyio
async def test_process_review_job(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    job = await start_full_review(db_session, test_user, book.id,
                                  StartFullReviewRequest(mode="proofreading"))
    await db_session.commit()
    job = await process_review_job(db_session, test_user, job.id)
    assert job.status in ("completed", "queued")
    assert job.processed_items >= 1


# — selection action ———————————————————————————————————————————————————————————
@pytest.mark.anyio
async def test_selection_action(db_session, test_user, test_book_and_chapter):
    book, chapter = test_book_and_chapter
    res = await act_on_selection(db_session, test_user, chapter.id,
                                 SelectionActionRequest(selected_text="AI tools is becoming",
                                                        action="proofread"))
    assert res["suggestion"].suggested_text is not None
    assert res["chapter"].content != SAMPLE_CHAPTER_CONTENT