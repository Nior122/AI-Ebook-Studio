"""KDP validation API endpoints."""

from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import CurrentUser, DatabaseSession
from schemas.kdp import KDPValidationReportResponse, KDPValidationSummary
from services.kdp.engine import get_kdp_validator

router = APIRouter(prefix="/book-writing/books", tags=["kdp-validation"])


@router.post(
    "/{book_id}/validate-kdp",
    response_model=KDPValidationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Run KDP validation on a book",
)
async def validate_book_kdp(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> KDPValidationReportResponse:
    """Run full KDP compliance checks and return a pass/fail report."""
    validator = get_kdp_validator()
    report = await validator.validate(session, user, book_id)
    return KDPValidationReportResponse.model_validate(report)


@router.get(
    "/{book_id}/validate-kdp",
    response_model=KDPValidationReportResponse,
    summary="Get latest KDP validation report",
)
async def get_kdp_report(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> KDPValidationReportResponse | None:
    """Return the most recent KDP validation report."""
    validator = get_kdp_validator()
    report = await validator.get_report(session, user, book_id)
    if report is None:
        return None
    return KDPValidationReportResponse.model_validate(report)