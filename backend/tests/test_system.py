"""Tests for backend infrastructure system endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    """Health endpoint returns a successful service status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"]
    assert payload["environment"]


@pytest.mark.asyncio
async def test_version_endpoint() -> None:
    """Version endpoint returns application version metadata."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["app"]
    assert payload["version"]
