"""AI model registry with provider metadata, capabilities, and cost tracking.

The registry is a singleton populated at import time. It maps every supported
model to its canonical ``provider/name`` key.

Usage::

    from services.models_registry import registry
    model = registry.get("openai/gpt-4o")
    assert model.supports_images
    print(model.context_length)  # 128_000
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from providers.ai.base import ModelCapability, ModelCapabilities


@dataclass(frozen=True)
class ModelInfo:
    """Compact metadata for an LLM."""

    provider: str
    name: str
    context_length: int | None = None
    max_output_tokens: int | None = None
    supports_images: bool = False
    supports_streaming: bool = True
    supports_json_mode: bool = False
    supports_tools: bool = False
    input_cost_per_1m_tokens: float = 0.0
    output_cost_per_1m_tokens: float = 0.0
    status: str = "active"
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        "Canonical registry key, e.g. ``openai/gpt-4o``."
        return f"{self.provider}/{self.name}"

    @property
    def capabilities(self) -> ModelCapabilities:
        """Normalized capability set for capability-aware checks."""
        return ModelCapabilities(
            text_generation=True,
            structured_output=self.supports_json_mode,
            streaming=self.supports_streaming,
            vision=self.supports_images,
            tool_calling=self.supports_tools,
        )

    def supports(self, capability: ModelCapability) -> bool:
        """Return whether this model provides *capability*."""
        return self.capabilities.supports(capability)

    def supports_vision(self) -> bool:
        return self.supports_images

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Return estimated cost in USD."""
        return (prompt_tokens / 1_000_000) * self.input_cost_per_1m_tokens + (
            completion_tokens / 1_000_000
        ) * self.output_cost_per_1m_tokens


class ModelRegistry:
    """Singleton registry of known models."""

    _instance: ClassVar[ModelRegistry | None] = None
    _models: dict[str, ModelInfo]

    # ------------------------------------------------------------------
    # singleton mechanics
    # ------------------------------------------------------------------
    def __new__(cls) -> ModelRegistry:  # noqa: D102
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._models = {}
            cls._instance._bootstrap()
        return cls._instance

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    @property
    def models(self) -> dict[str, ModelInfo]:
        return self._models.copy()

    def get(self, key: str) -> ModelInfo | None:
        return self._models.get(key)

    def by_provider(self, provider: str) -> list[ModelInfo]:
        return [m for m in self._models.values() if m.provider == provider]

    def all_keys(self) -> list[str]:
        return list(self._models.keys())

    def add(self, info: ModelInfo) -> None:
        self._models[info.key] = info

    def active_keys(self, provider: str | None = None) -> list[str]:
        """Return registry keys for active models, optionally filtered."""
        return [
            key
            for key, m in self._models.items()
            if m.status == "active" and (provider is None or m.provider == provider)
        ]

    def capabilities(self, key: str) -> dict[str, bool] | None:
        """Return the capability dict for *key*, or ``None`` if unknown."""
        info = self.get(key)
        return info.capabilities.to_dict() if info else None

    def find_with_capability(self, capability: ModelCapability) -> list[ModelInfo]:
        """Return active models that support *capability*."""
        return [m for m in self._models.values() if m.supports(capability)]

    # ------------------------------------------------------------------
    # built-in models
    # ------------------------------------------------------------------
    def _bootstrap(self) -> None:
        # ---- OpenAI ----
        self.add(
            ModelInfo(
                "openai",
                "gpt-4o",
                context_length=128_000,
                max_output_tokens=16_384,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=5.00,
                output_cost_per_1m_tokens=15.00,
            )
        )
        self.add(
            ModelInfo(
                "openai",
                "gpt-4o-mini",
                context_length=128_000,
                max_output_tokens=16_384,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=0.15,
                output_cost_per_1m_tokens=0.60,
            )
        )
        self.add(
            ModelInfo(
                "openai",
                "gpt-4-turbo",
                context_length=128_000,
                max_output_tokens=4096,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=10.00,
                output_cost_per_1m_tokens=30.00,
            )
        )
        self.add(
            ModelInfo(
                "openai",
                "gpt-3.5-turbo",
                context_length=16_385,
                max_output_tokens=4096,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=0.50,
                output_cost_per_1m_tokens=1.50,
            )
        )

        # ---- Anthropic ----
        self.add(
            ModelInfo(
                "anthropic",
                "claude-3-5-sonnet-20241022",
                context_length=200_000,
                max_output_tokens=8192,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=False,
                input_cost_per_1m_tokens=3.00,
                output_cost_per_1m_tokens=15.00,
            )
        )
        self.add(
            ModelInfo(
                "anthropic",
                "claude-3-5-haiku-20241022",
                context_length=200_000,
                max_output_tokens=8192,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=False,
                input_cost_per_1m_tokens=1.00,
                output_cost_per_1m_tokens=5.00,
            )
        )
        self.add(
            ModelInfo(
                "anthropic",
                "claude-3-opus-20240229",
                context_length=200_000,
                max_output_tokens=4096,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=False,
                input_cost_per_1m_tokens=15.00,
                output_cost_per_1m_tokens=75.00,
            )
        )

        # ---- Google Gemini ----
        self.add(
            ModelInfo(
                "gemini",
                "gemini-1.5-pro",
                context_length=1_000_000,
                max_output_tokens=8192,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=3.50,
                output_cost_per_1m_tokens=10.50,
            )
        )
        self.add(
            ModelInfo(
                "gemini",
                "gemini-1.5-flash",
                context_length=1_000_000,
                max_output_tokens=8192,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=0.35,
                output_cost_per_1m_tokens=1.05,
            )
        )
        self.add(
            ModelInfo(
                "gemini",
                "gemini-2.0-flash-exp",
                context_length=1_048_576,
                max_output_tokens=8192,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=0.00,
                output_cost_per_1m_tokens=0.00,
                tags=("experimental",),
            )
        )

        # ---- OpenRouter ----
        self.add(
            ModelInfo(
                "openrouter",
                "openai/gpt-4o",
                context_length=128_000,
                max_output_tokens=16_384,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=5.00,
                output_cost_per_1m_tokens=15.00,
            )
        )
        self.add(
            ModelInfo(
                "openrouter",
                "anthropic/claude-3.5-sonnet",
                context_length=200_000,
                max_output_tokens=8192,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=False,
                input_cost_per_1m_tokens=3.00,
                output_cost_per_1m_tokens=15.00,
            )
        )
        self.add(
            ModelInfo(
                "openrouter",
                "meta-llama/llama-3.3-70b-instruct",
                context_length=128_000,
                max_output_tokens=8192,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=False,
                input_cost_per_1m_tokens=0.40,
                output_cost_per_1m_tokens=0.60,
            )
        )
        self.add(
            ModelInfo(
                "openrouter",
                "google/gemini-1.5-pro",
                context_length=1_000_000,
                max_output_tokens=8192,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=3.50,
                output_cost_per_1m_tokens=10.50,
            )
        )
        self.add(
            ModelInfo(
                "openrouter",
                "x-ai/grok-2",
                context_length=128_000,
                max_output_tokens=8192,
                supports_images=True,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=2.00,
                output_cost_per_1m_tokens=10.00,
            )
        )

        # ---- Groq ----
        self.add(
            ModelInfo(
                "groq",
                "llama-3.3-70b-versatile",
                context_length=128_000,
                max_output_tokens=8192,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=0.59,
                output_cost_per_1m_tokens=0.79,
            )
        )
        self.add(
            ModelInfo(
                "groq",
                "llama-3.1-8b-instant",
                context_length=128_000,
                max_output_tokens=8192,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=0.05,
                output_cost_per_1m_tokens=0.08,
            )
        )
        self.add(
            ModelInfo(
                "groq",
                "mixtral-8x7b-32768",
                context_length=32_768,
                max_output_tokens=8192,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=0.27,
                output_cost_per_1m_tokens=0.27,
            )
        )
        self.add(
            ModelInfo(
                "groq",
                "gemma-2-9b-it",
                context_length=8_000,
                max_output_tokens=8192,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=True,
                input_cost_per_1m_tokens=0.20,
                output_cost_per_1m_tokens=0.20,
            )
        )

        # ---- Ollama ----
        self.add(
            ModelInfo(
                "ollama",
                "llama3.2",
                context_length=128_000,
                max_output_tokens=8192,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=False,
                input_cost_per_1m_tokens=0.00,
                output_cost_per_1m_tokens=0.00,
            )
        )
        self.add(
            ModelInfo(
                "ollama",
                "llama3.1",
                context_length=128_000,
                max_output_tokens=8192,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=False,
                input_cost_per_1m_tokens=0.00,
                output_cost_per_1m_tokens=0.00,
            )
        )
        self.add(
            ModelInfo(
                "ollama",
                "mistral",
                context_length=32_000,
                max_output_tokens=8192,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=False,
                input_cost_per_1m_tokens=0.00,
                output_cost_per_1m_tokens=0.00,
            )
        )
        self.add(
            ModelInfo(
                "ollama",
                "phi4",
                context_length=16_000,
                max_output_tokens=8192,
                supports_images=False,
                supports_streaming=True,
                supports_json_mode=False,
                input_cost_per_1m_tokens=0.00,
                output_cost_per_1m_tokens=0.00,
            )
        )


# singleton accessor
registry = ModelRegistry()

__all__ = [
    "ModelInfo",
    "ModelRegistry",
    "registry",
]
