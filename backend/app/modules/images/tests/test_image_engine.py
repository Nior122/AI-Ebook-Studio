"""Engine tests for image generation and versioning."""

from dataclasses import replace

import pytest

from app.modules.images.providers.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageProviderProtocol,
)
from app.modules.images.services.engine import ImageIntelligenceEngine


class MockImageProvider(ImageProviderProtocol):
    def __init__(self) -> None:
        self._counter = 0

    @property
    def name(self) -> str:
        return "pollinations"

    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self._counter += 1
        return ImageGenerationResult(
            image_url=f"https://example.com/{self._counter}.png",
            provider=self.name,
            model=request.model or "mock/model",
            seed=request.seed or self._counter,
            width=request.width,
            height=request.height,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=15.0,
            raw_response={"counter": self._counter},
        )

    async def regenerate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        return await self.generate_image(replace(request, seed=None))

    async def variations(self, request: ImageGenerationRequest) -> list[ImageGenerationResult]:
        return [await self.generate_image(request)]

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_provider_health_returns_configured_provider() -> None:
    engine = ImageIntelligenceEngine()
    engine._providers = {"pollinations": MockImageProvider()}  # noqa: SLF001

    health = await engine.provider_health()

    assert health == {"pollinations": True}
