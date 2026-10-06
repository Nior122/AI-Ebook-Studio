"""Translation endpoints for separate, source-preserving language editions."""

from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import AIServiceDep, CurrentUser, DatabaseSession
from schemas.translation import (
    TranslationEditionResponse,
    TranslationLanguage,
    TranslationListResponse,
    TranslationRecordResponse,
    TranslationRequest,
)
from services.translation.engine import SUPPORTED_LANGUAGES, get_translation_engine

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
    response_model=TranslationEditionResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or resume a translated edition",
)
async def translate_book(
    book_id: UUID,
    payload: TranslationRequest,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> TranslationEditionResponse:
    """Translate the selected source revision without changing its chapters."""
    engine = get_translation_engine(ai_service)
    edition = await engine.translate(
        session,
        user,
        book_id,
        payload.source_language,
        payload.target_language,
        translation_id=payload.translation_id,
    )
    return TranslationEditionResponse.model_validate(edition)


@router.get(
    "/{book_id}/translate/history",
    response_model=TranslationListResponse,
    summary="List translated editions",
)
async def list_translations(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> TranslationListResponse:
    engine = get_translation_engine(ai_service)
    records = await engine.get_translations(session, user, book_id)
    return TranslationListResponse(
        items=[TranslationRecordResponse.model_validate(record) for record in records]
    )


@router.get(
    "/{book_id}/translate/{translation_id}",
    response_model=TranslationEditionResponse,
    summary="Open a translated edition",
)
async def get_translation(
    book_id: UUID,
    translation_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> TranslationEditionResponse:
    """Load one translated edition and its target-language chapters."""
    engine = get_translation_engine(ai_service)
    edition = await engine.get_translation(session, user, book_id, translation_id)
    return TranslationEditionResponse.model_validate(edition)
