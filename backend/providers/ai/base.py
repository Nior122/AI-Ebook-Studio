"""Provider-agnostic AI types, interface, and normalized errors.

This module defines the contract every AI provider adapter must satisfy and the
normalized response/error shapes the rest of the application consumes. It is
deliberately free of any concrete provider SDK so features (writing engine,
analyzer, etc.) only ever depend on :class:`AIProvider` and :class:`AIResponse`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class AIProviderError(Exception):
    """Base class for all normalized AI provider failures.

    Carries enough structured context for the service layer to decide whether a
    retry or fallback is worthwhile, without leaking provider secrets.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        retryable: bool = True,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model
        self.retryable = retryable
        self.status_code = status_code

    def __str__(self) -> str:  # pragma: no cover - debug helper
        ctx = ", ".join(
            f"{k}={v}" for k, v in (("provider", self.provider), ("model", self.model)) if v
        )
        return f"{self.__class__.__name__}({ctx}): {self.message}"


class ProviderConfigurationError(AIProviderError):
    """Provider is misconfigured (missing/invalid base_url, no api key, etc.)."""


class ProviderAuthenticationError(AIProviderError):
    """API key missing, invalid, or expired."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", False)
        kwargs.setdefault("status_code", 401)
        super().__init__(message, **kwargs)


class ProviderRateLimitError(AIProviderError):
    """Rate limit / quota exceeded."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", True)
        kwargs.setdefault("status_code", 429)
        super().__init__(message, **kwargs)


class ProviderTimeoutError(AIProviderError):
    """Request exceeded the configured timeout."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", True)
        kwargs.setdefault("status_code", 504)
        super().__init__(message, **kwargs)


class ProviderUnavailableError(AIProviderError):
    """Provider endpoint unreachable or returned an unexpected transport error."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", True)
        kwargs.setdefault("status_code", 503)
        super().__init__(message, **kwargs)


class ModelNotFoundError(AIProviderError):
    """Requested model is unknown or not available for the provider."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", False)
        kwargs.setdefault("status_code", 404)
        super().__init__(message, **kwargs)


class UnsupportedCapabilityError(AIProviderError):
    """The selected model/provider does not support a required capability."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("retryable", False)
        kwargs.setdefault("status_code", 422)
        super().__init__(message, **kwargs)


class ProviderResponseError(AIProviderError):
    """Provider returned an unexpected / unparseable response."""


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------
class ModelCapability(str, Enum):
    """Discrete capabilities a model may support."""

    TEXT_GENERATION = "text_generation"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    VISION = "vision"
    TOOL_CALLING = "tool_calling"


# Map every capability to a friendly label for API responses.
CAPABILITY_LABELS: dict[ModelCapability, str] = {
    ModelCapability.TEXT_GENERATION: "Text generation",
    ModelCapability.STRUCTURED_OUTPUT: "Structured JSON output",
    ModelCapability.STREAMING: "Streaming",
    ModelCapability.VISION: "Vision / image understanding",
    ModelCapability.TOOL_CALLING: "Tool calling",
}


@dataclass(frozen=True)
class ModelCapabilities:
    """Normalized capability set for a model."""

    text_generation: bool = True
    structured_output: bool = False
    streaming: bool = False
    vision: bool = False
    tool_calling: bool = False

    def supports(self, capability: ModelCapability) -> bool:
        return getattr(self, capability.value, False)

    def to_dict(self) -> dict[str, bool]:
        return {
            "text_generation": self.text_generation,
            "structured_output": self.structured_output,
            "streaming": self.streaming,
            "vision": self.vision,
            "tool_calling": self.tool_calling,
        }

    @classmethod
    def from_flags(
        cls,
        *,
        text_generation: bool = True,
        structured_output: bool = False,
        streaming: bool = False,
        vision: bool = False,
        tool_calling: bool = False,
    ) -> ModelCapabilities:
        return cls(
            text_generation=text_generation,
            structured_output=structured_output,
            streaming=streaming,
            vision=vision,
            tool_calling=tool_calling,
        )


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Message:
    """Provider-independent chat message.

    Roles: ``system`` | ``user`` | ``assistant`` | ``tool``.
    """

    role: str
    content: str


# ---------------------------------------------------------------------------
# Generation config
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GenerationConfig:
    """Per-request generation parameters."""

    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stream: bool = False
    json_mode: bool = False
    timeout_seconds: float = 120.0
    retry_attempts: int = 0
    # Optional structured-output schema (JSON schema dict). When provided the
    # provider attempts to constrain output to this shape.
    response_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class GenerationRequest:
    """All data required to perform a generation."""

    messages: list[Message]
    model: str
    provider: str | None = None  # e.g. "openai" (inferred from model if absent)
    config: GenerationConfig = field(default_factory=GenerationConfig)
    system_prompt: str | None = None
    user_id: UUID | None = None
    project_id: UUID | None = None
    workspace_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Normalized response (provider-independent)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TokenUsage:
    """Canonical token accounting for a single generation."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class AIResponse:
    """Normalized, provider-independent generation result.

    This is the shape every application feature should consume. It deliberately
    mirrors the common ``{content, provider, model, usage, finish_reason,
    metadata}`` contract so no feature needs to understand a provider's raw API.
    """

    content: str
    provider: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Backwards-compatible alias used by some consumers."""
        return self.content


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------
class AIProvider(ABC):
    """Abstract interface every AI provider adapter must satisfy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical provider id, e.g. ``openai``."""

    @property
    def display_name(self) -> str:
        """Human-friendly provider name."""
        return self.name.title()

    # -- configuration / discovery -------------------------------------
    def validate_configuration(self) -> None:
        """Raise :class:`ProviderConfigurationError` if misconfigured.

        Default: no-op. Concrete adapters override when they require secrets or
        endpoints.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider looks reachable / configured."""

    async def get_available_models(self) -> list[str]:
        """Return model identifiers this provider currently offers."""
        return []

    # -- generation -----------------------------------------------------
    @abstractmethod
    async def generate_text(self, request: GenerationRequest) -> AIResponse:
        """Produce a single normalized completion."""

    async def generate_structured_output(
        self,
        request: GenerationRequest,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return JSON adhering to *schema*.

        Default implementation enables JSON mode and parses the returned text.
        Providers with native structured output should override.
        """
        cfg = GenerationConfig(
            temperature=request.config.temperature,
            max_tokens=request.config.max_tokens,
            top_p=request.config.top_p,
            stream=False,
            json_mode=True,
            timeout_seconds=request.config.timeout_seconds,
            response_schema=schema or request.config.response_schema,
        )
        resp = await self.generate_text(
            GenerationRequest(
                messages=request.messages,
                model=request.model,
                provider=request.provider,
                config=cfg,
                system_prompt=request.system_prompt,
                user_id=request.user_id,
                project_id=request.project_id,
                workspace_id=request.workspace_id,
                metadata=request.metadata,
            )
        )
        import json

        try:
            return json.loads(resp.content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ProviderResponseError(
                f"Provider did not return valid JSON: {exc}", provider=self.name
            ) from exc

    def stream_text(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Yield incremental text chunks. Providers must implement or raise."""
        raise NotImplementedError(f"{self.name} does not support streaming.")

    async def count_tokens_if_supported(self, text: str, model: str) -> int | None:
        """Return token count, or ``None`` if the provider cannot estimate."""
        try:
            return await self.count_tokens(text, model)
        except NotImplementedError:
            return None

    async def count_tokens(self, text: str, model: str) -> int:
        """Return an estimated token count for *text* under *model*."""
        return max(1, len(text) // 4)


# Backwards-compat aliases used by existing engine/tests/schemas.
AIProviderProtocol = AIProvider
AIError = AIProviderError
GenerationResponse = AIResponse
