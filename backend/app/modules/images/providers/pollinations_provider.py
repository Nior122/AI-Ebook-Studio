"""Pollinations image provider.

This adapter returns a reproducible provider URL without downloading or storing
binary image data. The Export Engine can consume the stored URL later.
"""

from __future__ import annotations

from random import randint
from time import perf_counter
from urllib.parse import quote

from app.modules.images.providers.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageProviderProtocol,
)


class PollinationsProvider(ImageProviderProtocol):
    """Pollinations adapter."""

    base_url = "https://image.pollinations.ai/prompt"

    @property
    def name(self) -> str:
        return "pollinations"

    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        started = perf_counter()
        seed = request.seed if request.seed is not None else randint(10_000, 999_999)
        url = self._build_url(request, seed)
        elapsed_ms = (perf_counter() - started) * 1000
        return ImageGenerationResult(
            image_url=url,
            provider=self.name,
            model=request.model or "pollinations/default",
            seed=seed,
            width=request.width,
            height=request.height,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=elapsed_ms,
            raw_response={"url": url, "seed": seed},
        )

    async def regenerate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        refreshed = ImageGenerationRequest(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            aspect_ratio=request.aspect_ratio,
            width=request.width,
            height=request.height,
            style=request.style,
            quality=request.quality,
            seed=None,
            model=request.model,
            metadata=request.metadata,
        )
        return await self.generate_image(refreshed)

    async def variations(self, request: ImageGenerationRequest) -> list[ImageGenerationResult]:
        return [await self.generate_image(request) for _ in range(3)]

    async def health_check(self) -> bool:
        return True

    def _build_url(self, request: ImageGenerationRequest, seed: int) -> str:
        encoded = quote(request.prompt, safe="")
        return (
            f"{self.base_url}/{encoded}"
            f"?width={request.width}&height={request.height}"
            f"&seed={seed}&nologo=true&safe=true"
        )
