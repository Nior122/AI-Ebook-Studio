# Image Workflow

## Provider Strategy

Image generation is separate from text AI generation. Pollinations is the first planned provider, with room for future providers.

## Planned Flow

```text
User request -> image service -> image provider interface -> provider adapter -> asset storage
```

## Design Rules

- Store prompt, provider, model, dimensions, seed, and usage metadata.
- Keep generated assets associated with projects.
- Do not expose provider-specific payloads directly to the frontend.

## Stage 1 Boundary

No image generation is implemented in this stage.
