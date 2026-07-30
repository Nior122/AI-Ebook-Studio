"""Image Intelligence Engine for planning, generation, placement, and versioning."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.images.generation.prompt_builder import build_image_prompt
from app.modules.images.models.image_models import (
    GeneratedImage,
    ImagePlacement,
    ImagePlan,
    ImageProvider,
    ImageVersion,
)
from app.modules.images.planning.analyzer import ChapterImageAnalysis, analyze_document
from app.modules.images.providers import (
    ImageGenerationRequest,
    ImageProviderProtocol,
    PollinationsProvider,
)
from app.modules.images.schemas.api import ImageAnalysisResponse
from app.modules.images.validators.rules import ensure_aspect_ratio, ensure_mode, ensure_style
from core.config import Settings, get_settings
from models.accounts import User
from models.document import (
    Chapter as ChapterModel,
)
from models.document import (
    Paragraph as ParagraphModel,
)
from models.document import (
    Part as PartModel,
)
from models.document import (
    Section as SectionModel,
)
from models.document import (
    Sentence as SentenceModel,
)
from models.operations import Job
from models.project import Book, ProjectSettings
from services.document_model import StructuredDocument, node
from services.project_service import get_project
from services.writing_engine import WritingEngine

logger = structlog.get_logger(__name__)


class ImageIntelligenceEngine:
    """Central Stage 8 service."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._providers: dict[str, ImageProviderProtocol] = {
            "pollinations": PollinationsProvider(),
        }

    async def analyze_book(
        self,
        session: AsyncSession,
        user: User,
        *,
        book_id: UUID,
        mode: str,
        custom_count: int | None = None,
    ) -> ImageAnalysisResponse:
        mode = ensure_mode(mode)
        book, project_settings = await self._get_book_bundle(session, user, book_id)
        doc = await self._load_structured_document(session, book)

        chapter_analysis = analyze_document(doc, mode=mode, custom_count=custom_count)
        total = sum(item.recommended_count for item in chapter_analysis)
        return ImageAnalysisResponse(
            book_id=book.id,
            chapters=[self._chapter_analysis_response(item) for item in chapter_analysis],
            total_recommended_images=total,
        )

    async def create_plan(
        self,
        session: AsyncSession,
        user: User,
        *,
        book_id: UUID,
        mode: str,
        custom_count: int | None = None,
        replace_existing: bool = True,
    ) -> list[ImagePlan]:
        analysis = await self.analyze_book(
            session,
            user,
            book_id=book_id,
            mode=mode,
            custom_count=custom_count,
        )
        book, project_settings = await self._get_book_bundle(session, user, book_id)

        if replace_existing:
            existing = await session.execute(
                select(ImagePlan).where(
                    ImagePlan.book_id == book_id, ImagePlan.deleted_at.is_(None)
                ),
            )
            for plan in existing.scalars():
                plan.deleted_at = datetime.now(UTC)
                plan.status = "superseded"

        plans: list[ImagePlan] = []
        for chapter in analysis.chapters:
            for suggestion in chapter.suggestions:
                prompt, negative_prompt = build_image_prompt(
                    subject=suggestion.subject,
                    chapter_title=suggestion.chapter_title,
                    section_title=suggestion.section_title,
                    paragraph_preview=suggestion.paragraph_preview,
                    style=ensure_style(project_settings.illustration_style, "Photorealistic"),
                    aspect_ratio=ensure_aspect_ratio(None, project_settings.image_ratio),
                    color_theme=project_settings.image_color_theme,
                    quality=project_settings.image_quality,
                )
                plans.append(
                    ImagePlan(
                        project_id=book.project_id,
                        book_id=book.id,
                        chapter_id=suggestion.chapter_id,
                        section_id=suggestion.section_id,
                        paragraph_id=suggestion.paragraph_id,
                        created_by_user_id=user.id,
                        mode=mode,
                        status="planned",
                        title=suggestion.section_title,
                        subject=suggestion.subject,
                        rationale=suggestion.rationale,
                        importance_score=suggestion.importance_score,
                        visual_complexity_score=suggestion.visual_complexity_score,
                        educational_value_score=suggestion.educational_value_score,
                        narrative_value_score=suggestion.narrative_value_score,
                        recommended_order=suggestion.recommended_order,
                        aspect_ratio=ensure_aspect_ratio(None, project_settings.image_ratio),
                        style=ensure_style(project_settings.illustration_style, "Photorealistic"),
                        color_theme=project_settings.image_color_theme,
                        quality=project_settings.image_quality,
                        prompt=prompt,
                        negative_prompt=negative_prompt,
                        metadata_json={"paragraph_preview": suggestion.paragraph_preview},
                    )
                )
        session.add_all(plans)
        await session.commit()
        return plans

    async def generate(
        self,
        session: AsyncSession,
        user: User,
        *,
        plan_id: UUID,
        provider_name: str,
        model: str | None,
        title: str | None,
        style: str | None,
        aspect_ratio: str | None,
        quality: str | None,
        prompt_override: str | None,
        negative_prompt_override: str | None,
        seed: int | None,
    ) -> tuple[GeneratedImage, Job]:
        plan = await self._get_plan(session, user, plan_id)
        provider = self._resolve_provider(provider_name)
        provider_row = await self._ensure_provider_record(session, provider)
        job = Job(
            user_id=user.id,
            project_id=plan.project_id,
            job_type="image.generate",
            status="queued",
            payload={"plan_id": str(plan.id), "provider": provider.name},
        )
        session.add(job)
        await session.flush()
        job.status = "generating"

        resolved_style = ensure_style(style, plan.style)
        resolved_ratio = ensure_aspect_ratio(aspect_ratio, plan.aspect_ratio)
        resolved_quality = quality or plan.quality
        width, height = _dimensions_for_ratio(resolved_ratio)
        generation_request = ImageGenerationRequest(
            prompt=prompt_override or plan.prompt or plan.subject,
            negative_prompt=negative_prompt_override or plan.negative_prompt or "",
            aspect_ratio=resolved_ratio,
            width=width,
            height=height,
            style=resolved_style,
            quality=resolved_quality,
            seed=seed,
            model=model or "pollinations/default",
            metadata={"plan_id": str(plan.id)},
        )
        result = await provider.generate_image(generation_request)

        image = GeneratedImage(
            project_id=plan.project_id,
            book_id=plan.book_id,
            created_by_user_id=user.id,
            plan_id=plan.id,
            provider_id=provider_row.id,
            status="completed",
            title=title or plan.title,
            alt_text=plan.subject,
            aspect_ratio=resolved_ratio,
            style=resolved_style,
            quality=resolved_quality,
            model_name=result.model,
            provider_name=result.provider,
            seed=result.seed,
            width=result.width,
            height=result.height,
            current_version_number=1,
            current_image_url=result.image_url,
            metadata_json={"importance_score": plan.importance_score},
        )
        session.add(image)
        await session.flush()

        placement = ImagePlacement(
            project_id=plan.project_id,
            book_id=plan.book_id,
            chapter_id=plan.chapter_id,
            section_id=plan.section_id,
            paragraph_id=plan.paragraph_id,
            plan_id=plan.id,
            generated_image_id=image.id,
            alignment="center",
            caption=plan.title,
            display_width=result.width,
            display_height=result.height,
            aspect_ratio=result.aspect_ratio,
            position="after_paragraph",
            placement_order=plan.recommended_order,
            placement_label="after_paragraph",
            confidence_score=plan.importance_score,
        )
        version = ImageVersion(
            generated_image_id=image.id,
            provider_id=provider_row.id,
            version_number=1,
            source_type="generated",
            status="completed",
            prompt=generation_request.prompt,
            negative_prompt=generation_request.negative_prompt,
            provider_name=result.provider,
            model_name=result.model,
            seed=result.seed,
            width=result.width,
            height=result.height,
            aspect_ratio=result.aspect_ratio,
            generation_time_ms=result.generation_time_ms,
            image_url=result.image_url,
            metadata_json=result.raw_response,
        )
        session.add_all([placement, version])
        plan.status = "generated"
        job.status = "completed"
        job.result = {"image_id": str(image.id), "version_number": 1}
        await session.commit()
        return await self.get_image_entity(session, user, image.id), job

    async def regenerate(
        self,
        session: AsyncSession,
        user: User,
        *,
        image_id: UUID,
        provider_name: str | None,
        model: str | None,
        style: str | None,
        aspect_ratio: str | None,
        quality: str | None,
        prompt_override: str | None,
        negative_prompt_override: str | None,
        seed: int | None,
    ) -> tuple[GeneratedImage, Job]:
        image = await self.get_image_entity(session, user, image_id)
        latest = _latest_version(image)
        provider = self._resolve_provider(provider_name or image.provider_name or "pollinations")
        provider_row = await self._ensure_provider_record(session, provider)
        job = Job(
            user_id=user.id,
            project_id=image.project_id,
            job_type="image.regenerate",
            status="queued",
            payload={"image_id": str(image.id), "provider": provider.name},
        )
        session.add(job)
        await session.flush()
        job.status = "generating"

        resolved_style = ensure_style(style, image.style)
        resolved_ratio = ensure_aspect_ratio(aspect_ratio, image.aspect_ratio)
        resolved_quality = quality or image.quality
        width, height = _dimensions_for_ratio(resolved_ratio)
        request = ImageGenerationRequest(
            prompt=prompt_override or latest.prompt,
            negative_prompt=negative_prompt_override or latest.negative_prompt,
            aspect_ratio=resolved_ratio,
            width=width,
            height=height,
            style=resolved_style,
            quality=resolved_quality,
            seed=seed,
            model=model or latest.model_name,
            metadata={"image_id": str(image.id)},
        )
        result = await provider.regenerate(request)
        next_version = image.current_version_number + 1
        session.add(
            ImageVersion(
                generated_image_id=image.id,
                provider_id=provider_row.id,
                version_number=next_version,
                source_type="regenerated",
                status="completed",
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                provider_name=result.provider,
                model_name=result.model,
                seed=result.seed,
                width=result.width,
                height=result.height,
                aspect_ratio=result.aspect_ratio,
                generation_time_ms=result.generation_time_ms,
                image_url=result.image_url,
                metadata_json=result.raw_response,
            )
        )
        image.current_version_number = next_version
        image.current_image_url = result.image_url
        image.provider_id = provider_row.id
        image.provider_name = result.provider
        image.model_name = result.model
        image.seed = result.seed
        image.width = result.width
        image.height = result.height
        image.style = resolved_style
        image.aspect_ratio = resolved_ratio
        image.quality = resolved_quality
        job.status = "completed"
        job.result = {"image_id": str(image.id), "version_number": next_version}
        await session.commit()
        return await self.get_image_entity(session, user, image.id), job

    async def replace(
        self,
        session: AsyncSession,
        user: User,
        *,
        image_id: UUID,
        image_url: str,
        prompt: str | None,
        negative_prompt: str | None,
        model: str,
    ) -> tuple[GeneratedImage, Job]:
        image = await self.get_image_entity(session, user, image_id)
        latest = _latest_version(image)
        job = Job(
            user_id=user.id,
            project_id=image.project_id,
            job_type="image.replace",
            status="queued",
            payload={"image_id": str(image.id)},
        )
        session.add(job)
        await session.flush()
        next_version = image.current_version_number + 1
        session.add(
            ImageVersion(
                generated_image_id=image.id,
                provider_id=image.provider_id,
                version_number=next_version,
                source_type="replaced",
                status="completed",
                prompt=prompt or latest.prompt,
                negative_prompt=negative_prompt or latest.negative_prompt,
                provider_name=image.provider_name or "external",
                model_name=model,
                seed=image.seed,
                width=image.width or latest.width,
                height=image.height or latest.height,
                aspect_ratio=image.aspect_ratio,
                generation_time_ms=0.0,
                image_url=image_url,
                metadata_json={"manual_replace": True},
            )
        )
        image.current_version_number = next_version
        image.current_image_url = image_url
        image.status = "completed"
        job.status = "completed"
        await session.commit()
        return await self.get_image_entity(session, user, image.id), job

    async def restore_version(
        self,
        session: AsyncSession,
        user: User,
        *,
        image_id: UUID,
        version_number: int,
    ) -> GeneratedImage:
        image = await self.get_image_entity(session, user, image_id)
        source = next(
            (version for version in image.versions if version.version_number == version_number),
            None,
        )
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image version not found.",
            )
        next_version = image.current_version_number + 1
        session.add(
            ImageVersion(
                generated_image_id=image.id,
                provider_id=image.provider_id,
                version_number=next_version,
                source_type="restored",
                status="completed",
                prompt=source.prompt,
                negative_prompt=source.negative_prompt,
                provider_name=source.provider_name,
                model_name=source.model_name,
                seed=source.seed,
                width=source.width,
                height=source.height,
                aspect_ratio=source.aspect_ratio,
                generation_time_ms=0.0,
                image_url=source.image_url,
                metadata_json={"restored_from_version": version_number},
            )
        )
        image.current_version_number = next_version
        image.current_image_url = source.image_url
        image.provider_name = source.provider_name
        image.model_name = source.model_name
        image.seed = source.seed
        image.width = source.width
        image.height = source.height
        image.aspect_ratio = source.aspect_ratio
        await session.commit()
        return await self.get_image_entity(session, user, image.id)

    async def list_images(
        self,
        session: AsyncSession,
        user: User,
        *,
        project_id: UUID | None = None,
        book_id: UUID | None = None,
    ) -> list[GeneratedImage]:
        statement = (
            select(GeneratedImage)
            .options(
                selectinload(GeneratedImage.placement),
                selectinload(GeneratedImage.versions),
            )
            .where(GeneratedImage.deleted_at.is_(None))
            .order_by(GeneratedImage.created_at.desc())
        )
        if book_id is not None:
            book, _settings = await self._get_book_bundle(session, user, book_id)
            statement = statement.where(GeneratedImage.book_id == book.id)
        elif project_id is not None:
            project = await get_project(session, user, project_id)
            statement = statement.where(GeneratedImage.project_id == project.id)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="project_id or book_id is required.",
            )
        result = await session.execute(statement)
        return list(result.scalars())

    async def get_image_entity(
        self,
        session: AsyncSession,
        user: User,
        image_id: UUID,
    ) -> GeneratedImage:
        result = await session.execute(
            select(GeneratedImage)
            .options(
                selectinload(GeneratedImage.placement),
                selectinload(GeneratedImage.versions),
            )
            .where(GeneratedImage.id == image_id, GeneratedImage.deleted_at.is_(None))
        )
        image = result.scalar_one_or_none()
        if image is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
        await get_project(session, user, image.project_id)
        return image

    async def update_image(
        self,
        session: AsyncSession,
        user: User,
        *,
        image_id: UUID,
        title: str | None,
        alt_text: str | None,
        status_value: str | None,
        restore_version_number: int | None,
    ) -> GeneratedImage:
        if restore_version_number is not None:
            return await self.restore_version(
                session,
                user,
                image_id=image_id,
                version_number=restore_version_number,
            )
        image = await self.get_image_entity(session, user, image_id)
        if title is not None:
            image.title = title
        if alt_text is not None:
            image.alt_text = alt_text
        if status_value is not None:
            image.status = status_value
        await session.commit()
        return await self.get_image_entity(session, user, image_id)

    async def delete_image(self, session: AsyncSession, user: User, *, image_id: UUID) -> None:
        image = await self.get_image_entity(session, user, image_id)
        image.deleted_at = datetime.now(UTC)
        image.status = "deleted"
        await session.commit()

    async def provider_health(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name, provider in self._providers.items():
            results[name] = await provider.health_check()
        return results

    async def _load_structured_document(
        self,
        session: AsyncSession,
        book: Book,
    ) -> StructuredDocument:
        doc = await WritingEngine.load_from_db(session, book.project_id, book.id)
        if doc is not None:
            return doc

        doc = StructuredDocument.new_book(book.project_id, book.id, book.title)
        root = doc.root

        parts_result = await session.execute(
            select(PartModel)
            .where(PartModel.book_id == book.id, PartModel.deleted_at.is_(None))
            .order_by(PartModel.position)
        )
        for part_row in parts_result.scalars():
            root.add_child(
                node(
                    "part",
                    id=part_row.id,
                    title=part_row.title,
                    position=part_row.position,
                    status=part_row.status,
                )
            )

        chapters_result = await session.execute(
            select(ChapterModel)
            .where(ChapterModel.book_id == book.id, ChapterModel.deleted_at.is_(None))
            .order_by(ChapterModel.position)
        )
        for chapter_row in chapters_result.scalars():
            chapter_node = node(
                "chapter",
                id=chapter_row.id,
                title=chapter_row.title,
                position=chapter_row.position,
                status=chapter_row.status,
            )
            if chapter_row.part_id is not None:
                part_node = root.find(chapter_row.part_id)
                if part_node is not None:
                    part_node.add_child(chapter_node)
                else:
                    root.add_child(chapter_node)
            else:
                root.add_child(chapter_node)

        sections_result = await session.execute(
            select(SectionModel)
            .where(SectionModel.book_id == book.id, SectionModel.deleted_at.is_(None))
            .order_by(SectionModel.position)
        )
        for section_row in sections_result.scalars():
            found_chapter_node = root.find(section_row.chapter_id)
            if found_chapter_node is None:
                continue
            found_chapter_node.add_child(
                node(
                    "section",
                    id=section_row.id,
                    title=section_row.title or "",
                    position=section_row.position,
                    status=section_row.status,
                )
            )

        paragraphs_result = await session.execute(
            select(ParagraphModel)
            .where(ParagraphModel.book_id == book.id, ParagraphModel.deleted_at.is_(None))
            .order_by(ParagraphModel.position)
        )
        for paragraph_row in paragraphs_result.scalars():
            found_section_node = root.find(paragraph_row.section_id)
            if found_section_node is None:
                continue
            found_section_node.add_child(
                node(
                    "paragraph",
                    id=paragraph_row.id,
                    kind=paragraph_row.kind,
                    position=paragraph_row.position,
                    status=paragraph_row.status,
                )
            )

        sentences_result = await session.execute(
            select(SentenceModel)
            .where(SentenceModel.book_id == book.id, SentenceModel.deleted_at.is_(None))
            .order_by(SentenceModel.position)
        )
        for sentence_row in sentences_result.scalars():
            found_paragraph_node = root.find(sentence_row.paragraph_id)
            if found_paragraph_node is None:
                continue
            found_paragraph_node.add_child(
                node(
                    "sentence",
                    id=sentence_row.id,
                    text=sentence_row.text,
                    kind=sentence_row.kind,
                    position=sentence_row.position,
                    status=sentence_row.status,
                )
            )

        return doc

    async def _get_book_bundle(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
    ) -> tuple[Book, ProjectSettings]:
        result = await session.execute(
            select(Book).where(Book.id == book_id, Book.deleted_at.is_(None))
        )
        book = result.scalar_one_or_none()
        if book is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found.")
        project = await get_project(session, user, book.project_id)
        settings_result = await session.execute(
            select(ProjectSettings).where(ProjectSettings.project_id == project.id),
        )
        settings = settings_result.scalar_one_or_none()
        if settings is None:
            settings = ProjectSettings(project_id=project.id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return book, settings

    async def _get_plan(self, session: AsyncSession, user: User, plan_id: UUID) -> ImagePlan:
        result = await session.execute(
            select(ImagePlan).where(ImagePlan.id == plan_id, ImagePlan.deleted_at.is_(None))
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image plan not found.",
            )
        await get_project(session, user, plan.project_id)
        return plan

    async def _ensure_provider_record(
        self,
        session: AsyncSession,
        provider: ImageProviderProtocol,
    ) -> ImageProvider:
        result = await session.execute(
            select(ImageProvider).where(ImageProvider.name == provider.name)
        )
        row = result.scalar_one_or_none()
        healthy = await provider.health_check()
        if row is None:
            row = ImageProvider(
                name=provider.name,
                display_name=provider.name.title(),
                api_base_url=getattr(provider, "base_url", None),
                is_enabled=True,
            )
            session.add(row)
            await session.flush()
        row.last_health_status = healthy
        row.last_health_check_at = datetime.now(UTC)
        return row

    def _resolve_provider(self, provider_name: str) -> ImageProviderProtocol:
        provider = self._providers.get(provider_name)
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Image provider '{provider_name}' is not configured.",
            )
        return provider

    @staticmethod
    def _chapter_analysis_response(item: ChapterImageAnalysis) -> Any:
        return {
            "chapter_id": item.chapter_id,
            "chapter_title": item.chapter_title,
            "recommended_count": item.recommended_count,
            "suggestions": [
                {
                    "chapter_id": suggestion.chapter_id,
                    "chapter_title": suggestion.chapter_title,
                    "section_id": suggestion.section_id,
                    "section_title": suggestion.section_title,
                    "paragraph_id": suggestion.paragraph_id,
                    "paragraph_preview": suggestion.paragraph_preview,
                    "subject": suggestion.subject,
                    "rationale": suggestion.rationale,
                    "importance_score": suggestion.importance_score,
                    "visual_complexity_score": suggestion.visual_complexity_score,
                    "educational_value_score": suggestion.educational_value_score,
                    "narrative_value_score": suggestion.narrative_value_score,
                    "recommended_order": suggestion.recommended_order,
                }
                for suggestion in item.suggestions
            ],
        }


def _dimensions_for_ratio(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "1:1":
        return (1200, 1200)
    if aspect_ratio == "9:16":
        return (1080, 1920)
    if aspect_ratio == "4:3":
        return (1600, 1200)
    if aspect_ratio == "3:2":
        return (1500, 1000)
    return (1600, 900)


def _latest_version(image: GeneratedImage) -> ImageVersion:
    if not image.versions:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Image has no versions.")
    return max(image.versions, key=lambda version: version.version_number)


def get_image_engine(settings: Settings | None = None) -> ImageIntelligenceEngine:
    """Return a configured image engine."""
    return ImageIntelligenceEngine(settings=settings)
