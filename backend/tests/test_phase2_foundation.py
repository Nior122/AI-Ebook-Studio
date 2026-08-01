"""Phase 2 backend foundation tests.

Covers the infrastructure introduced/confirmed in Phase 2:
health contract, configuration loading, the error envelope, security utilities,
the AI/image/storage provider interfaces, and the job abstraction. These are
real behavior tests (no always-pass assertions).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from core.config import Settings, get_settings
from core.exceptions import ResourceNotFoundError, error_response
from core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from providers.ai.base import AIProviderProtocol, GenerationRequest, Message
from providers.storage.base import StorageObject, StorageProviderProtocol
from providers.storage.local_provider import LocalStorageProvider
from services.jobs import InMemoryJobQueue, JobStatus, JobType


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_returns_service_and_version() -> None:
    """Health endpoint returns status, service, and version per the Phase 2 contract."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == get_settings().service_name
    assert payload["version"] == get_settings().app_version


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def test_settings_load_defaults() -> None:
    """Settings load with the expected Phase 2 fields present."""
    settings = get_settings()
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.jwt_algorithm == "HS256"
    assert settings.storage_provider == "local"
    assert settings.db_pool_size >= 1


def test_settings_google_key_alias() -> None:
    """GOOGLE_AI_API_KEY is accepted as an alias for the canonical Google key."""
    settings = Settings(google_ai_api_key="alias-key")
    assert settings.resolved_google_api_key == "alias-key"
    settings2 = Settings(google_api_key="primary-key")
    assert settings2.resolved_google_api_key == "primary-key"


def test_settings_parse_cors_from_string() -> None:
    """CORS origins parse from a comma-separated string."""
    settings = Settings(cors_origins="http://a.com, http://b.com")
    assert settings.cors_origins == ["http://a.com", "http://b.com"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
def test_error_response_envelope_shape() -> None:
    """The error envelope always includes success=false and a code/message."""
    body = error_response("RESOURCE_NOT_FOUND", "missing")
    assert body["success"] is False
    error = body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "RESOURCE_NOT_FOUND"
    assert error["message"] == "missing"


def test_app_error_carries_status_and_code() -> None:
    """Domain errors expose their HTTP status and stable code."""
    err = ResourceNotFoundError("nope")
    assert err.status_code == 404
    assert err.code == "RESOURCE_NOT_FOUND"
    assert str(err) == "nope"


# ---------------------------------------------------------------------------
# Security utilities
# ---------------------------------------------------------------------------
def test_password_hash_roundtrip() -> None:
    """Passwords hash and verify correctly, and wrong passwords fail."""
    hashed = hash_password("Sup3rSecret!")
    assert hashed != "Sup3rSecret!"
    assert verify_password("Sup3rSecret!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_jwt_create_and_decode_roundtrip() -> None:
    """A created access token decodes back to the original subject id."""
    settings = get_settings()
    user_id = uuid.uuid4()
    token, expires_at = create_access_token(user_id, settings)
    assert isinstance(token, str) and token.count(".") == 2
    decoded = decode_access_token(token, settings)
    assert decoded == user_id
    assert expires_at is not None


def test_jwt_rejects_tampered_token() -> None:
    """A tampered token fails to decode."""
    import jwt as pyjwt

    settings = get_settings()
    token, _ = create_access_token(uuid.uuid4(), settings)
    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token(token + "tampered", settings)


# ---------------------------------------------------------------------------
# AI provider interface
# ---------------------------------------------------------------------------
def test_ai_provider_interface_is_abstract() -> None:
    """The AI provider protocol cannot be instantiated directly."""
    with pytest.raises(TypeError):
        AIProviderProtocol()  # type: ignore[abstract]


def test_ai_generation_request_construction() -> None:
    """A generation request holds messages and a model specifier."""
    request = GenerationRequest(
        messages=[Message(role="user", content="hi")],
        model="openai/gpt-4o-mini",
    )
    assert request.model == "openai/gpt-4o-mini"
    assert request.messages[0].content == "hi"
    assert request.config.temperature == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Image provider interface
# ---------------------------------------------------------------------------
def test_image_provider_interface_is_abstract() -> None:
    """The image provider protocol cannot be instantiated directly."""
    from app.modules.images.providers.base import (
        ImageGenerationRequest,
        ImageProviderProtocol,
    )

    with pytest.raises(TypeError):
        ImageProviderProtocol()  # type: ignore[abstract]

    req = ImageGenerationRequest(prompt="a cat", negative_prompt="")
    assert req.aspect_ratio == "16:9"
    assert req.width > 0 and req.height > 0


# ---------------------------------------------------------------------------
# Storage provider interface
# ---------------------------------------------------------------------------
def test_storage_provider_interface_is_abstract() -> None:
    """The storage provider protocol cannot be instantiated directly."""
    with pytest.raises(TypeError):
        StorageProviderProtocol()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_local_storage_roundtrip(tmp_path: object) -> None:
    """Local storage saves, reads, checks existence, and deletes objects."""
    provider = LocalStorageProvider(root=str(tmp_path))
    assert provider.name == "local"
    assert await provider.health_check() is True

    stored = await provider.save(
        StorageObject(key="docs/hello.txt", data=b"hello", content_type="text/plain")
    )
    assert stored.size_bytes == 5
    assert stored.provider == "local"

    assert await provider.exists("docs/hello.txt") is True
    assert await provider.get("docs/hello.txt") == b"hello"

    await provider.delete("docs/hello.txt")
    assert await provider.exists("docs/hello.txt") is False


@pytest.mark.asyncio
async def test_local_storage_missing_object_raises(tmp_path: object) -> None:
    """Reading a missing object raises a not-found storage error."""
    from providers.storage.base import StorageObjectNotFoundError

    provider = LocalStorageProvider(root=str(tmp_path))
    with pytest.raises(StorageObjectNotFoundError):
        await provider.get("nope.txt")


# ---------------------------------------------------------------------------
# Job abstraction
# ---------------------------------------------------------------------------
def test_job_enums_are_complete() -> None:
    """All required job types and statuses exist."""
    assert JobType.BOOK_GENERATION.value == "BOOK_GENERATION"
    assert JobType.EPUB_EXPORT in set(JobType)
    assert JobStatus.COMPLETED.is_terminal is True
    assert JobStatus.RUNNING.is_terminal is False


@pytest.mark.asyncio
async def test_in_memory_job_queue_lifecycle() -> None:
    """The in-memory queue enqueues, retrieves, and cancels jobs."""
    queue = InMemoryJobQueue()
    assert queue.name == "memory"
    assert await queue.health_check() is True

    handle = await queue.enqueue(JobType.PDF_EXPORT, payload={"book_id": "x"})
    assert handle.status is JobStatus.QUEUED

    fetched = await queue.get(handle.id)
    assert fetched is not None and fetched.id == handle.id

    assert await queue.cancel(handle.id) is True
    cancelled = await queue.get(handle.id)
    assert cancelled is not None and cancelled.status is JobStatus.CANCELLED

    # Cancelling a terminal job returns False.
    assert await queue.cancel(handle.id) is False


@pytest.mark.asyncio
async def test_jobs_endpoint_returns_404_for_unknown_job(client: AsyncClient) -> None:
    """The jobs endpoint returns the standard error envelope for unknown ids.

    Since the hardening pass, job endpoints require authentication and are
    scoped to the caller; unknown ids still surface as RESOURCE_NOT_FOUND.
    """
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"phase2-{uuid.uuid4().hex[:8]}@test.dev",
            "password": "SecurePass123",
            "display_name": "Phase 2 QA",
        },
    )
    assert registered.status_code in (200, 201), registered.text
    token = registered.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Unauthenticated access is rejected before any lookup happens.
    anon = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert anon.status_code == 401

    response = await client.get(f"/api/v1/jobs/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_books_routes_replaced_by_phase3_endpoints() -> None:
    """The Phase 2 placeholder is gone; real book access requires auth (401/404)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/books/00000000-0000-0000-0000-000000000000")

    assert response.status_code in (401, 404)
