"""System endpoint response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health endpoint response.

    Includes both machine-readable identifiers (``service``, ``version``) used by
    monitoring/load balancers and human-friendly context (``app``, ``environment``).
    """

    status: str
    service: str
    version: str
    app: str
    environment: str
    timestamp: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "ai-ebook-studio-api",
                "version": "1.0.0",
            }
        }
    )


class VersionResponse(BaseModel):
    """Version endpoint response."""

    app: str
    version: str
    environment: str
