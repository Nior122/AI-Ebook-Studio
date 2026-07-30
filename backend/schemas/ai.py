"""API schemas for the AI Engine endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------
# Request / response models
# -----------------------------------------------------------------------
class ChatMessage(BaseModel):
    """A single chat message."""

    role: str = Field(description="system | user | assistant | tool")
    content: str


class GenerationConfigSchema(BaseModel):
    """Generation parameters."""

    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stream: bool = False
    json_mode: bool = False
    timeout_seconds: float = 120.0
    retry_attempts: int = 0


class ChatRequest(BaseModel):
    """Chat/completion request."""

    messages: list[ChatMessage]
    model: str | None = Field(default=None, description="e.g. 'openai/gpt-4o' or 'gpt-4o'")
    provider: str | None = Field(default=None, description=" Explicit provider override")
    system_prompt: str | None = None
    config: GenerationConfigSchema = Field(default_factory=GenerationConfigSchema)


class CompletionRequest(BaseModel):
    """Single-prompt completion request."""

    prompt: str
    model: str | None = None
    provider: str | None = None
    system_prompt: str | None = None
    config: GenerationConfigSchema = Field(default_factory=GenerationConfigSchema)


class StructuredRequest(BaseModel):
    """Structured (JSON) generation request."""

    messages: list[ChatMessage]
    response_schema: dict[str, Any] = Field(description="JSON schema the output must conform to.")
    model: str | None = None
    provider: str | None = None
    system_prompt: str | None = None
    task: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None


class UsageSchema(BaseModel):
    """Token and cost usage for a single generation."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class GenerationResponse(BaseModel):
    """Canonical AI generation response."""

    content: str
    provider: str
    model: str
    finish_reason: str | None = None
    usage: UsageSchema
    latency_ms: float

    model_config = ConfigDict(from_attributes=True)


class ProviderSchema(BaseModel):
    """Provider metadata response (no secrets)."""

    name: str
    available: bool = True
    healthy: bool = False
    models: list[str] = Field(default_factory=list)
    requires_key: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "openai",
                "available": True,
                "healthy": True,
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
                "requires_key": True,
            }
        }
    )


class ModelInfoSchema(BaseModel):
    """Model metadata response."""

    key: str
    provider: str
    name: str
    display_name: str
    context_window: int | None
    max_output_tokens: int | None
    supports_streaming: bool
    supports_structured_output: bool
    supports_tools: bool
    supports_vision: bool
    status: str = "active"
    input_cost_per_1m_tokens: float = 0.0
    output_cost_per_1m_tokens: float = 0.0
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "openai/gpt-4o",
                "provider": "openai",
                "name": "gpt-4o",
                "display_name": "gpt-4o",
                "context_window": 128000,
                "max_output_tokens": 16384,
                "supports_streaming": True,
                "supports_structured_output": True,
                "supports_tools": True,
                "supports_vision": True,
                "status": "active",
                "input_cost_per_1m_tokens": 5.0,
                "output_cost_per_1m_tokens": 15.0,
                "tags": [],
            }
        }
    )


class CapabilitiesSchema(BaseModel):
    """Capability matrix for a model (no secrets)."""

    key: str
    provider: str
    name: str
    capabilities: dict[str, bool]
    context_window: int | None = None


class HealthStatus(BaseModel):
    """AI system health report."""

    overall: str  # "ok" | "degraded" | "unavailable"
    providers: dict[str, bool]
    timestamp: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall": "ok",
                "providers": {"openai": True, "anthropic": False},
                "timestamp": "2025-01-01T12:00:00Z",
            }
        }
    )


class AIProviderPreferenceSchema(BaseModel):
    """User AI provider preferences (selections only — never secrets)."""

    preferred_provider: str | None = None
    preferred_model: str | None = None
    fallback_provider: str | None = None
    fallback_model: str | None = None
    temperature: float = 0.7
    default_writing_style: str | None = None
    default_language: str | None = "en"
    stream_responses: bool = True

    model_config = ConfigDict(from_attributes=True)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall": "ok",
                "providers": {"openai": True, "anthropic": False},
                "timestamp": "2025-01-01T12:00:00Z",
            }
        },
    )


class AISystemStatus(BaseModel):
    """Overall AI system status."""

    status: str
    providers_available: int
    timestamp: datetime
