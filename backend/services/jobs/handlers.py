"""Job handlers for async operations.

Each handler wraps an existing engine call, reporting progress 0–100 via
the supplied callback. The handler is invoked by the runner after a job
is enqueued and updated to RUNNING.

Handlers are registered via :func:`register_all_handlers` at application
startup so the in-process worker pool knows how to execute each JobType.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.accounts import User
from services.cover.engine import get_cover_engine
from services.export.engine import get_export_engine
from services.generation.orchestrator import generation_handler
from services.jobs.enums import JobType
from services.jobs.runner import ProgressCallback, register_handler


def _payload_user(payload: dict[str, object]) -> tuple[UUID | None, UUID | None]:
    """Extract (user_id, book_id) from a job payload dict."""
    user_id = payload.get("user_id")
    book_id = payload.get("book_id")
    return (
        UUID(str(user_id)) if user_id else None,
        UUID(str(book_id)) if book_id else None,
    )


async def _load_user(session: AsyncSession, user_id: UUID) -> User:
    """Load an authenticated job owner from the database."""
    from sqlalchemy import select as sa_select

    result = await session.execute(sa_select(User).where(User.id == user_id))
    user = result.scalar()
    if user is None:
        raise ValueError(f"User {user_id} not found.")
    return user


async def _export_handler(
    session: AsyncSession,
    job_id: UUID,
    payload: dict[str, object],
    progress: ProgressCallback,
) -> dict[str, object] | None:
    """Generate an export file (DOCX/PDF/EPUB) for a book."""
    await progress(5, "Preparing export")
    user_id, book_id = _payload_user(payload)
    if not user_id or not book_id:
        raise ValueError("Export job missing user_id or book_id.")
    user = await _load_user(session, user_id)

    await progress(10, "Loading chapters")
    fmt = str(payload.get("format", "docx"))
    include_front_matter = bool(payload.get("include_front_matter", True))
    include_toc = bool(payload.get("include_toc", True))
    include_back_matter = bool(payload.get("include_back_matter", True))

    await progress(50, f"Rendering {fmt.upper()}")
    engine = get_export_engine()
    asset = await engine.export_book(
        session=session,
        user=user,
        book_id=book_id,
        fmt=fmt,
        include_front_matter=include_front_matter,
        include_toc=include_toc,
        include_back_matter=include_back_matter,
    )

    await progress(95, "Finalizing")
    await progress(100, "Export complete")
    return {
        "asset_id": str(asset.id),
        "format": fmt,
        "file_name": asset.file_name,
        "file_size": asset.file_size,
    }


async def _kdp_validation_handler(
    session: AsyncSession,
    job_id: UUID,
    payload: dict[str, object],
    progress: ProgressCallback,
) -> dict[str, object] | None:
    """Run KDP validation checks on a book."""
    from services.kdp.engine import KDPValidator

    await progress(10, "Loading book and chapters")
    user_id, book_id = _payload_user(payload)
    if not user_id or not book_id:
        raise ValueError("KDP validation job missing user_id or book_id.")
    user = await _load_user(session, user_id)

    await progress(40, "Running margin and font checks")
    await progress(70, "Running image and layout checks")
    await progress(90, "Compiling report")
    validator = KDPValidator()
    report = await validator.validate(session=session, user=user, book_id=book_id)
    await progress(100, "Validation complete")
    return {
        "report_id": str(report.id),
        "status": report.status,
        "issues_count": len(report.issues or []),
    }


async def _cover_handler(
    session: AsyncSession,
    job_id: UUID,
    payload: dict[str, object],
    progress: ProgressCallback,
) -> dict[str, object] | None:
    """Generate cover design content (front, back, spine)."""
    await progress(5, "Preparing cover design")
    user_id, book_id = _payload_user(payload)
    if not user_id or not book_id:
        raise ValueError("Cover job missing user_id or book_id.")
    user = await _load_user(session, user_id)

    component = str(payload.get("component", "all"))
    if component not in {"front", "back", "spine", "all"}:
        raise ValueError(f"Unsupported cover component '{component}'.")

    from services.ai_service import AIService

    engine = get_cover_engine(AIService())
    results: dict[str, object] = {}

    if component in {"front", "all"}:
        await progress(20, "Generating front cover")
        results["front"] = await engine.generate_front_cover(session, user, book_id)

    if component in {"back", "all"}:
        await progress(50, "Generating back cover")
        results["back"] = await engine.generate_back_cover(session, user, book_id)

    if component in {"spine", "all"}:
        await progress(80, "Generating spine")
        results["spine"] = await engine.generate_spine(session, user, book_id)

    await progress(100, "Cover complete")
    return results


async def _marketing_handler(
    session: AsyncSession,
    job_id: UUID,
    payload: dict[str, object],
    progress: ProgressCallback,
) -> dict[str, object] | None:
    """Generate a marketing asset for a book."""
    from models.enums import MarketingAssetType
    from services.ai_service import AIService
    from services.marketing.engine import get_marketing_engine

    user_id, book_id = _payload_user(payload)
    if not user_id or not book_id:
        raise ValueError("Marketing job missing user_id or book_id.")
    user = await _load_user(session, user_id)

    asset_type_str = str(payload.get("asset_type", "amazon_description"))
    try:
        asset_type = MarketingAssetType(asset_type_str)
    except ValueError as error:
        raise ValueError(f"Unsupported marketing asset type '{asset_type_str}'.") from error

    await progress(15, f"Generating {asset_type.value}")
    engine = get_marketing_engine(AIService())
    asset = await engine.generate(
        session=session, user=user, book_id=book_id, asset_type_str=asset_type.value
    )
    await progress(100, "Marketing asset ready")
    return {
        "asset_id": str(asset.id) if hasattr(asset, "id") else None,
        "asset_type": asset_type.value,
    }


async def _translation_handler(
    session: AsyncSession,
    job_id: UUID,
    payload: dict[str, object],
    progress: ProgressCallback,
) -> dict[str, object] | None:
    """Translate a source revision into a separate, resumable edition."""
    from services.ai_service import AIService
    from services.translation.engine import get_translation_engine

    user_id, book_id = _payload_user(payload)
    if not user_id or not book_id:
        raise ValueError("Translation job missing user_id or book_id.")
    user = await _load_user(session, user_id)

    source_lang = str(payload.get("source_lang", "en"))
    target_lang = str(payload.get("target_lang", "es"))
    raw_translation_id = payload.get("translation_id")
    translation_id = UUID(str(raw_translation_id)) if raw_translation_id else None

    edition = await get_translation_engine(AIService()).translate(
        session,
        user,
        book_id,
        source_lang,
        target_lang,
        translation_id=translation_id,
        progress=progress,
    )
    return {
        "translation_id": str(edition.id),
        "chapters_translated": edition.translated_chapter_count,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "status": edition.status,
    }


def register_all_handlers() -> None:
    """Register all built-in job handlers."""
    register_handler(JobType.DOCX_BUILD, _export_handler)
    register_handler(JobType.PDF_EXPORT, _export_handler)
    register_handler(JobType.EPUB_EXPORT, _export_handler)
    register_handler(JobType.KDP_VALIDATION, _kdp_validation_handler)
    register_handler(JobType.COVER_GENERATION, _cover_handler)
    register_handler(JobType.MARKETING_GENERATION, _marketing_handler)
    register_handler(JobType.TRANSLATION, _translation_handler)
    register_handler(JobType.BOOK_GENERATION, generation_handler)
