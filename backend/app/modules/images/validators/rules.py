"""Validation helpers for image inputs."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.modules.images.planning.analyzer import ASPECT_RATIOS, IMAGE_COUNT_MODES, IMAGE_STYLES


def ensure_mode(mode: str) -> str:
    if mode not in IMAGE_COUNT_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image planning mode."
        )
    return mode


def ensure_aspect_ratio(aspect_ratio: str | None, fallback: str) -> str:
    candidate = aspect_ratio or fallback
    aliases = {"square": "1:1", "portrait": "9:16", "landscape": "16:9"}
    candidate = aliases.get(candidate, candidate)
    if candidate not in ASPECT_RATIOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid aspect ratio."
        )
    return candidate


def ensure_style(style: str | None, fallback: str) -> str:
    candidate = style or fallback
    if candidate not in IMAGE_STYLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image style."
        )
    return candidate
