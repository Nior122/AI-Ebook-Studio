"""Integration tests for the Image Intelligence Engine API."""

from uuid import UUID, uuid4

import pytest
from _pytest.monkeypatch import MonkeyPatch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.images.providers.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageProviderProtocol,
)
from app.modules.images.services.engine import ImageIntelligenceEngine
from models.document import Chapter, Paragraph, Section, Sentence


class MockImageProvider(ImageProviderProtocol):
    def __init__(self) -> None:
        self.counter = 0

    @property
    def name(self) -> str:
        return "pollinations"

    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self.counter += 1
        return ImageGenerationResult(
            image_url=f"https://example.com/generated-{self.counter}.png",
            provider=self.name,
            model=request.model or "mock/model",
            seed=request.seed or self.counter,
            width=request.width,
            height=request.height,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=20.0,
            raw_response={"counter": self.counter},
        )

    async def regenerate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        return await self.generate_image(request)

    async def variations(self, request: ImageGenerationRequest) -> list[ImageGenerationResult]:
        return [await self.generate_image(request)]

    async def health_check(self) -> bool:
        return True


async def register_and_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 201
    return str(response.json()["tokens"]["access_token"])


@pytest.mark.asyncio
async def test_image_api_flow(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    engine = ImageIntelligenceEngine()
    engine._providers = {"pollinations": MockImageProvider()}  # noqa: SLF001
    monkeypatch.setattr("app.modules.images.controllers.router.get_image_engine", lambda: engine)

    token = await register_and_token(client, "images@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    workspaces = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = workspaces.json()[0]["id"]
    project = await client.post(
        "/api/v1/projects",
        json={"workspace_id": workspace_id, "name": "Images Project"},
        headers=headers,
    )
    assert project.status_code == 201
    project_id = UUID(project.json()["id"])

    book = await client.post(
        f"/api/v1/projects/{project_id}/books",
        json={"title": "Illustrated Book"},
        headers=headers,
    )
    assert book.status_code == 201
    book_id = UUID(book.json()["id"])

    chapter_id = uuid4()
    section_id = uuid4()
    paragraph_id = uuid4()
    sentence_id = uuid4()
    db_session.add(
        Chapter(
            id=chapter_id,
            project_id=project_id,
            book_id=book_id,
            title="How systems work",
            slug="how-systems-work",
            position=1,
            summary="System overview",
            status="draft",
            word_count=12,
        )
    )
    db_session.add(
        Section(
            id=section_id,
            project_id=project_id,
            book_id=book_id,
            chapter_id=chapter_id,
            title="Step by step example",
            position=1,
            status="draft",
            word_count=12,
        )
    )
    db_session.add(
        Paragraph(
            id=paragraph_id,
            project_id=project_id,
            book_id=book_id,
            chapter_id=chapter_id,
            section_id=section_id,
            kind="body",
            position=1,
            status="draft",
            word_count=12,
        )
    )
    db_session.add(
        Sentence(
            id=sentence_id,
            project_id=project_id,
            book_id=book_id,
            chapter_id=chapter_id,
            section_id=section_id,
            paragraph_id=paragraph_id,
            text="This process and example should be visualized with a clear diagram.",
            kind="body",
            position=1,
            status="draft",
        )
    )
    await db_session.commit()

    analysis = await client.post(
        "/api/v1/images/analyze",
        json={"book_id": str(book_id), "mode": "automatic"},
        headers=headers,
    )
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["total_recommended_images"] >= 1

    plan = await client.post(
        "/api/v1/images/plan",
        json={"book_id": str(book_id), "mode": "automatic", "replace_existing": True},
        headers=headers,
    )
    assert plan.status_code == 200, plan.text
    plan_id = plan.json()[0]["id"]

    generated = await client.post(
        "/api/v1/images/generate",
        json={"plan_id": plan_id, "provider": "pollinations"},
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    image_id = generated.json()["image"]["id"]
    assert generated.json()["image"]["current_version_number"] == 1

    regenerated = await client.post(
        "/api/v1/images/regenerate",
        json={"image_id": image_id},
        headers=headers,
    )
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()["image"]["current_version_number"] == 2

    replaced = await client.post(
        "/api/v1/images/replace",
        json={"image_id": image_id, "image_url": "https://example.com/manual.png"},
        headers=headers,
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["image"]["current_version_number"] == 3

    listed = await client.get(f"/api/v1/images?book_id={book_id}", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = await client.get(f"/api/v1/images/{image_id}", headers=headers)
    assert fetched.status_code == 200
    assert len(fetched.json()["versions"]) == 3
    assert fetched.json()["placement"]["generated_image_id"] == image_id
    assert fetched.json()["placement"]["alignment"] == "center"
    assert fetched.json()["placement"]["caption"] == "Step by step example"
    assert fetched.json()["placement"]["display_width"] == 1600
    assert fetched.json()["placement"]["display_height"] == 900
    assert fetched.json()["placement"]["aspect_ratio"] == "16:9"
    assert fetched.json()["placement"]["position"] == "after_paragraph"

    restored = await client.put(
        f"/api/v1/images/{image_id}",
        json={"restore_version_number": 1},
        headers=headers,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["current_version_number"] == 4

    deleted = await client.delete(f"/api/v1/images/{image_id}", headers=headers)
    assert deleted.status_code == 200
