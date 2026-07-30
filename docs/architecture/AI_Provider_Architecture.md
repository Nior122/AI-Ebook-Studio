# AI Provider Architecture

## Principle

**No business code calls OpenAI, Anthropic, Gemini, OpenRouter, Groq, or Ollama
directly.** All text generation goes through the AI provider abstraction and the
`AIEngine`. This lets providers/models change without touching feature code.

## Components

```text
AIEngine (services/ai_engine.py)
  └── AIProviderProtocol (providers/ai/base.py)
        ├── OpenAIProvider
        ├── AnthropicProvider
        ├── GeminiProvider
        ├── OpenRouterProvider
        ├── GroqProvider
        └── OllamaProvider (local models)
```

### `providers/ai/base.py`

Defines the vendor-neutral contract and canonical data types:

- `AIProviderProtocol` — abstract interface: `generate_text`, `stream_text`,
  `count_tokens`, `available_models`, `health_check`, `name`.
- `GenerationRequest` / `GenerationConfig` — messages, model, temperature,
  max tokens, top_p, streaming, json mode, timeouts, retries, system prompt.
- `GenerationResponse` / `TokenUsage` — normalized output and token accounting.
- Typed error hierarchy: `AIError`, `ModelNotFoundError`,
  `ProviderAuthenticationError`, `ProviderRateLimitError`,
  `ProviderUnavailableError`, `ProviderResponseError`.

### `services/ai_engine.py`

The single entry point for all AI features:

- Resolves a provider from a `provider/model` specifier (e.g. `openai/gpt-4o`).
- Retries transient failures with linear backoff.
- Cascades to fallback providers when the primary fails.
- Injects cost estimates via the model registry.
- Provides `generate()`, `stream()`, and `health()`.

## Capabilities supported by the interface

Text generation, structured JSON generation (`json_mode`), streaming responses,
model selection, temperature, max tokens, and system instructions.

## Configuration

Provider API keys come from settings (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GOOGLE_API_KEY`/`GOOGLE_AI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`,
`OLLAMA_BASE_URL`). Only providers with configured keys are initialized;
`AI_DEFAULT_PROVIDER` / `AI_DEFAULT_MODEL` select defaults.

## Adding a provider

1. Implement `AIProviderProtocol` in `providers/ai/<name>_provider.py`.
2. Export it from `providers/ai/__init__.py`.
3. Register it in `AIEngine._PROVIDER_FACTORY`.

No feature code changes are required.
