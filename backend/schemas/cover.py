"""Cover generation schemas."""

from __future__ import annotations

from pydantic import BaseModel


class CoverComponentResponse(BaseModel):
    """A single cover component (front/back/spine)."""

    content: str
    type: str


class CoverAllResponse(BaseModel):
    """All cover components together."""

    front: CoverComponentResponse
    back: CoverComponentResponse
    spine: CoverComponentResponse