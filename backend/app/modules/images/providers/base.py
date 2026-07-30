"""Provider-agnostic image generation contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ImageProviderError(Exception):
    """Base image provider exception."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider


@dataclass(frozen=True)
class ImageGenerationRequest:
    """Canonical image generation request."""

    prompt: str
    negative_prompt: str
    aspect_ratio: str = "16:9"
    width: int = 1600
    height: int = 900
    style: str = "Photorealistic"
    quality: str = "high"
    seed: int | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageGenerationResult:
    """Canonical image generation result."""

    image_url: str
    provider: str
    model: str
    seed: int | None
    width: int
    height: int
    aspect_ratio: str
    generation_time_ms: float
    raw_response: dict[str, Any] = field(default_factory=dict)


class ImageProviderProtocol(ABC):
    """Interface every image provider must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical provider name."""

    @abstractmethod
    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate a new image."""

    @abstractmethod
    async def regenerate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Regenerate an image with fresh randomness or overrides."""

    @abstractmethod
    async def variations(self, request: ImageGenerationRequest) -> list[ImageGenerationResult]:
        """Return alternative variants for a prompt."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return provider health."""
