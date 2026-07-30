# Stage 5 Backend: Provider-Independent AI Engine

## Scope

Stage 5 creates the reusable AI infrastructure layer for future product features.

Not included:
- Ebook writing
- Editing
- Translation
- Marketing
- Image generation
- Cover generation
- DOCX/PDF/EPUB export

## Architecture

All future AI features should call `AIEngine.generate()` or `AIEngine.stream()`.
Feature code must not call OpenAI, Anthropic, Gemini, OpenRouter, Groq, Ollama,
or future provider APIs directly.

## Provider Interface

Every provider implements:
- `generate_text()`
- `stream_text()`
- `count_tokens()`
- `available_models()`
- `health_check()`

Current providers:
- OpenAI
- Anthropic
- Google Gemini
- OpenRouter
- Groq
- Ollama

Provider compatibility packages are available under `backend/app/providers/`.
Concrete adapters currently live in `backend/providers/ai/`.

## AI Engine Responsibilities

The AI engine handles:
- Provider selection
- Model selection
- Retry attempts
- Fallback provider routing
- Streaming support
- Structured logging hooks
- Usage/cost enrichment through the model registry
- Provider-independent errors

## Prompt Engine

`PromptEngine` supports:
- System prompt and user prompt composition
- Variable injection
- Template rendering
- Prompt registration
- Versioned prompt foundation

## Model Registry

`services/models_registry.py` stores model metadata:
- Provider
- Model name
- Context length
- Max output tokens
- Image support
- Streaming support
- JSON mode support
- Input/output cost metadata

## Project AI Settings

Project settings now include:
- `preferred_ai_provider`
- `preferred_ai_model`
- `ai_temperature`
- `ai_max_tokens`
- Existing writing language and writing style fields

## API

Public discovery/status:
- `GET /api/v1/ai/providers`
- `GET /api/v1/ai/models`
- `GET /api/v1/ai/status`

Authenticated generation infrastructure:
- `POST /api/v1/ai/test`
- `POST /api/v1/ai/chat`
- `POST /api/v1/ai/complete`

The chat and completion endpoints use an explicit body wrapper:

```json
{
  "payload": {
    "prompt": "Say OK",
    "model": "openai/gpt-4o-mini"
  }
}
```

## Telemetry

`ai_usage_records` tracks:
- User, workspace, and project references
- Provider and model
- Request type
- Prompt tokens
- Completion tokens
- Total tokens
- Estimated cost
- Latency
- Finish reason
- Error and retry fields for future hardening

## Testing

Stage 5 uses mocked providers. Tests verify:
- Provider switching
- Fallback behavior
- Streaming chunks
- AI status/model endpoints
- Authenticated completion endpoint

