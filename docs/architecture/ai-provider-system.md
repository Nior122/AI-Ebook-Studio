# AI Provider System

## Architecture

The AI Provider System is a provider-agnostic abstraction layer that decouples the application from any single LLM vendor. It supports **plugin-style provider registration**, **capability-based model selection**, **automatic fallback**, and **centralised orchestration**.

### Layers

```
API Layer (api/v1/ai.py)
    |
    v
AIService / AIEngine  (services/ai_service.py, services/ai_engine.py)
    |
    v
ProviderRegistry     (providers/ai/registry.py)
    |
    v
AIProvider interface (providers/ai/base.py)
    |         |         |         |         |
    v         v         v         v         v
 OpenAI   Anthropic   Gemini    Ollama   OpenAICompatible*
    |         |         |         |         |
    v         v         v         v         v
                                      OpenRouter / Groq / NvidiaNim / Custom
```

### Key Components

**AIProvider (base.py)** — Abstract interface all providers implement:
- `generate()` / `stream()` / `generate_structured()`
- `validate_configuration()` / `get_available_models()` / `health()`
- Capability-aware via `ModelCapabilities` flags

**ProviderRegistry (registry.py)** — Singleton that:
- Auto-discovers providers from environment settings on `load_from_settings()`
- Skips providers with missing API keys (no crash)
- Exposes `get()`, `list()`, `available()`, `validate()` methods

**AIService (ai_service.py)** — Central orchestrator:
- Resolves provider/model from string key (e.g. `openai/gpt-4o`)
- Validates capability requirements
- Executes with automatic fallback on failure
- Normalises all responses to `AIResponse`

**ModelRegistry (services/models_registry.py)** — Extended with:
- `capabilities` property returning `ModelCapabilities`
- `supports(ModelCapability)` per model
- `find_with_capability()` for capability-aware lookups
- `active_keys()` returning available model keys

### Provider Implementations

| Provider | Class | Requires Key | Notes |
|----------|-------|-------------|-------|
| OpenAI | `OpenAIProvider` | Yes | gpt-4o, gpt-4o-mini, gpt-4-turbo |
| Anthropic | `AnthropicProvider` | Yes | claude-3-5-sonnet, claude-3-opus, claude-3-haiku |
| Gemini | `GeminiProvider` | Yes | gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-flash |
| Ollama | `OllamaProvider` | No | Local, supports any installed model |
| OpenRouter | `OpenRouterProvider` | Yes | Routes through user API key |
| Groq | `GroqProvider` | Yes | Fast inference via Groq hardware |
| NvidiaNim | `NvidiaNimProvider` | Yes | Nvidia NIM microservices |
| Custom | `CustomOpenAIProvider` | Configurable | Any OpenAI-compatible endpoint |

### Error Handling

Defined in `providers/ai/base.py`:
- `ProviderError` (base)
- `AuthenticationError` — bad/missing API key
- `RateLimitError` — rate limited (retryable)
- `ContextLengthError` — context exceeded
- `ContentFilterError` — content blocked
- `ServiceUnavailableError` — provider down (retryable)
- `TimeoutError` — request timed out (retryable)
- `InvalidRequestError` — malformed request

Retryable errors trigger automatic fallback in AIService.

### Configuration

Environment variables (in `.env` or settings):
- `openai_api_key`, `anthropic_api_key`, `google_api_key`, `groq_api_key`, `openrouter_api_key`, `nvidia_nim_api_key`, `custom_openai_api_key`
- `custom_openai_base_url`, `custom_openai_model`
- `ai_fallback_provider`, `ai_fallback_model`

### User Preferences

Stored per-user in `ai_provider_preferences` table:
- Preferred provider/model
- Fallback provider/model
- Temperature, writing style, language, stream toggle
- Never stores API keys
