# AI API

Base path: `/api/v1/ai` — all endpoints require authentication.

## Provider Discovery

### `GET /ai/providers`

Returns configured providers with availability and model names.

```json
[
  {
    "name": "openai",
    "available": true,
    "healthy": false,
    "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "requires_key": true
  }
]
```

### `GET /ai/models`

Returns every model across configured providers with capability flags.

```json
[
  {
    "key": "openai/gpt-4o",
    "provider": "openai",
    "name": "gpt-4o",
    "context_window": 128000,
    "max_output_tokens": 16384,
    "supports_streaming": true,
    "supports_structured_output": true,
    "supports_tools": true,
    "supports_vision": true,
    "status": "active",
    "input_cost_per_1m_tokens": 5.0,
    "output_cost_per_1m_tokens": 15.0,
    "tags": []
  }
]
```

### `GET /ai/capabilities`

Returns capability matrix for every available model — lets UI disable features unsupported by the selected model.

```json
[
  {
    "key": "openai/gpt-4o",
    "provider": "openai",
    "name": "gpt-4o",
    "capabilities": {
      "streaming": true,
      "structured_output": true,
      "tool_calls": true,
      "parallel_tool_calls": true,
      "vision": true,
      "image_generation": false,
      "audio": false,
      "code_execution": false
    },
    "context_window": 128000
  }
]
```

## Generation

### `POST /ai/chat`

Multi-turn chat generation. Body must be wrapped in `{"payload": {...}}`.

```json
{
  "payload": {
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "openai/gpt-4o-mini",
    "provider": null,
    "config": {"temperature": 0.7}
  }
}
```

### `POST /ai/complete`

Single-prompt completion. Body wrapped in `{"payload": {...}}`.

### `POST /ai/structured`

Generate JSON conforming to a provided schema. Body wrapped in `{"payload": {...}}`.

```json
{
  "payload": {
    "messages": [{"role": "user", "content": "List 3 colors"}],
    "response_schema": {"type": "object", "properties": {"colors": {"type": "array", "items": {"type": "string"}}}},
    "model": "openai/gpt-4o-mini"
  }
}
```

### `POST /ai/test`

Quick health test — sends `"Hello"` to `openai/gpt-4o-mini`.

## Status

### `GET /ai/status`

```json
{
  "overall": "ok",
  "providers": {"openai": true, "anthropic": false},
  "timestamp": "2026-07-20T13:00:00Z"
}
```

## User Preferences

### `GET /ai/preferences`

Returns current user's AI provider preferences (no secrets).

### `PUT /ai/preferences`

Create or update preferences. Body wrapped in `{"payload": {...}}`.

```json
{
  "payload": {
    "preferred_provider": "openai",
    "preferred_model": "gpt-4o",
    "fallback_provider": "anthropic",
    "fallback_model": "claude-3-5-sonnet-latest",
    "temperature": 0.7,
    "default_writing_style": "balanced",
    "default_language": "en",
    "stream_responses": true
  }
}
```

## Response Format

All generation endpoints return:

```json
{
  "content": "Generated text...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "finish_reason": "stop",
  "usage": {
    "input_tokens": 25,
    "output_tokens": 100,
    "total_tokens": 125,
    "estimated_cost_usd": 0.002
  },
  "latency_ms": 1234.56
}
```

## Error Codes

| Code | Meaning |
|------|---------|
| `AUTHENTICATION_REQUIRED` | Missing/invalid token |
| `PROVIDER_NOT_FOUND` | Requested provider not configured |
| `MODEL_NOT_FOUND` | Requested model not registered |
| `CAPABILITY_NOT_SUPPORTED` | Model doesn't support required capability |
| `ALL_PROVIDERS_FAILED` | Primary and all fallbacks failed |
