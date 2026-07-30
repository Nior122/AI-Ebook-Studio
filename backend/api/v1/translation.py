"""Translation API endpoints."""

from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import AIServiceDep, CurrentUser, DatabaseSession
from schemas.book_writing import ChapterRead
from schemas.translation import TranslationRequest, TranslationRecordResponse, TranslationListResponse, TranslationLanguage
from services.translation.engine import get_translation_engine, SUPPORTED_LANGUAGES

router = APIRouter(prefix="/book-writing/books", tags=["translation"])


@router.get(
    "/{book_id}/translate/languages",
    response_model=list[TranslationLanguage],
    summary="List supported translation languages",
)
async def list_languages() -> list[TranslationLanguage]:
    return [TranslationLanguage(code=code, name=name) for code, name in SUPPORTED_LANGUAGES.items()]


@router.post(
    "/{book_id}/translate",
    response_model=list[ChapterRead],
    status_code=status.HTTP_200_OK,
    summary="Translate a book",
)
async def translate_book(
    book_id: UUID,
    payload: TranslationRequest,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> list[ChapterRead]:
    engine = get_translation_engine(ai_service)
    chapters = await engine.translate(
        session, user, book_id, payload.source_language, payload.target_language
    )
    return [ChapterRead.model_validate(c) for c in chapters]


@router.get(
    "/{book_id}/translate/history",
    response_model=TranslationListResponse,
    summary="List translation history",
)
async def list_translations(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> TranslationListResponse:
    engine = get_translation_engine(ai_service)
    records = await engine.get_translations(session, user, book_id)
    return TranslationListResponse(items=[TranslationRecordResponse.model_validate(r) for r in records])