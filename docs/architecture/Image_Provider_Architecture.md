# Image Provider Architecture

## Principle

Image generation is abstracted behind a provider interface so backends can be
switched (Pollinations first, others later) without changing feature code.

## Components

```text
ImageProviderProtocol (app/modules/images/providers/base.py)
  ├── PollinationsProvider  (first implementation)
  └── FutureProvider        (add without changing callers)
```

> Note: the canonical image provider interface currently lives under
> `app/modules/images/providers/`. `backend/providers/images/` is reserved for
> future consolidation. The abstraction and Pollinations implementation already
> exist from a prior stage; Phase 2 documents them.

### Interface

`ImageProviderProtocol` defines:

- `generate_image(request) -> ImageGenerationResult`
- `regenerate(request) -> ImageGenerationResult`
- `variations(request) -> list[ImageGenerationResult]`
- `health_check() -> bool`
- `name` (property)

### Request / result types

`ImageGenerationRequest` supports:

- `prompt`, `negative_prompt`
- `aspect_ratio` (default `16:9`)
- `width`, `height` (custom dimensions)
- `style`, `quality`, `seed`, `model`, `metadata`

`ImageGenerationResult` returns the image URL, provider, model, seed, dimensions,
aspect ratio, generation time, and the raw provider response.

## Capabilities

16:9 by default, custom width/height, future styles, and future provider
switching — all expressed through the request/result contract.

## Adding a provider

Implement `ImageProviderProtocol` in a new module and wire it into the image
engine's provider selection. Feature code that depends only on the protocol
requires no changes.
