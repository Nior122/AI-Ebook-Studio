"""AI provider adapters package.

Import shortcuts for concrete providers and shared base types::

    from providers.ai import OpenAIProvider, AnthropicProvider, GeminiProvider
    from providers.ai import OpenRouterProvider, GroqProvider, OllamaProvider
    from providers.ai import CustomOpenAIProvider, NvidiaNimProvider
    from providers.ai import AIProvider, AIResponse, AIProviderError
"""

from providers.ai.anthropic_provider import AnthropicProvider
from providers.ai.base import (
    AIProvider,
    AIProviderError,
    AIResponse,
    GenerationConfig,
    GenerationRequest,
    Message,
    ModelCapability,
    ModelCapabilities,
    TokenUsage,
)
from providers.ai.custom_openai_provider import (
    CustomOpenAIProvider,
    GroqProvider,
    NvidiaNimProvider,
    OpenAICompatibleProvider,
    OpenRouterProvider,
)
from providers.ai.gemini_provider import GeminiProvider
from providers.ai.ollama_provider import OllamaProvider
from providers.ai.openai_provider import OpenAIProvider

__all__ = [
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "OpenRouterProvider",
    "GroqProvider",
    "OllamaProvider",
    "CustomOpenAIProvider",
    "NvidiaNimProvider",
    "OpenAICompatibleProvider",
    # base types
    "AIProvider",
    "AIProviderError",
    "AIResponse",
    "GenerationConfig",
    "GenerationRequest",
    "Message",
    "ModelCapability",
    "ModelCapabilities",
    "TokenUsage",
]
