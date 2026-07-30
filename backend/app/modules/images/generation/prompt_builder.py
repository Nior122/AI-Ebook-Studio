"""Prompt builder for professional image prompts."""

from __future__ import annotations

from app.modules.images.planning.analyzer import ASPECT_RATIOS


def build_image_prompt(
    *,
    subject: str,
    chapter_title: str,
    section_title: str,
    paragraph_preview: str,
    style: str,
    aspect_ratio: str,
    color_theme: str | None,
    quality: str,
) -> tuple[str, str]:
    """Return a positive prompt and negative prompt."""
    resolved_ratio = aspect_ratio if aspect_ratio in ASPECT_RATIOS else "16:9"
    palette = color_theme or "balanced cinematic neutrals with intentional accent colors"
    prompt = (
        f"Subject: {subject}. "
        f"Environment: inspired by the chapter '{chapter_title}' and section '{section_title}'. "
        f"Camera: editorial wide composition suited for book interior illustration. "
        f"Lighting: soft, readable, premium studio-grade lighting. "
        f"Composition: clear focal point, uncluttered background, export-friendly framing. "
        f"Mood: confident, polished, instructive. "
        f"Color Palette: {palette}. "
        f"Style: {style}. "
        f"Aspect Ratio: {resolved_ratio}. "
        f"Quality: {quality}. "
        f"Context: {paragraph_preview}"
    )
    negative = (
        "low resolution, blurry, watermark, text overlay, distorted anatomy, cropped subject, "
        "extra limbs, duplicate objects, noisy background, unreadable details"
    )
    return prompt, negative
