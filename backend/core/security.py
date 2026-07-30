"""Authentication and token security helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from core.config import Settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_token(token: str) -> str:
    """Hash an opaque token before persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_opaque_token() -> str:
    """Create a secure random opaque token."""
    return secrets.token_urlsafe(48)


def create_access_token(user_id: UUID, settings: Settings) -> tuple[str, datetime]:
    """Create a signed JWT access token."""
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, expires_at


def decode_access_token(token: str, settings: Settings) -> UUID:
    """Decode and validate a JWT access token."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return UUID(str(payload["sub"]))


def password_policy_errors(password: str) -> list[str]:
    """Return password policy violations."""
    errors: list[str] = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not any(char.isupper() for char in password):
        errors.append("Password must include an uppercase letter.")
    if not any(char.islower() for char in password):
        errors.append("Password must include a lowercase letter.")
    if not any(char.isdigit() for char in password):
        errors.append("Password must include a number.")
    return errors


# ---------------------------------------------------------------------------
# Clerk JWT verification
# ---------------------------------------------------------------------------

_clerk_jwks_cache: dict[str, dict[str, Any]] = {}
_clerk_jwks_expires_at: float = 0


async def _fetch_clerk_jwks(settings: Settings) -> dict[str, dict[str, Any]]:
    """Fetch and cache Clerk JWKS keys, keyed by ``kid``."""
    global _clerk_jwks_cache, _clerk_jwks_expires_at
    now = datetime.now(UTC).timestamp()
    if _clerk_jwks_cache and now < _clerk_jwks_expires_at:
        return _clerk_jwks_cache

    jwks_url = settings.clerk_jwks_url
    if not jwks_url:
        raise ValueError("CLERK_JWKS_URL is not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        jwks = resp.json()

    cache: dict[str, dict[str, Any]] = {}
    for key in jwks.get("keys", []):
        kid = key.get("kid")
        if kid:
            cache[kid] = key

    _clerk_jwks_cache.clear()
    _clerk_jwks_cache.update(cache)
    _clerk_jwks_expires_at = now + 3600
    return cache


async def verify_clerk_token(token: str, settings: Settings) -> dict[str, Any]:
    """Verify a Clerk-issued session JWT and return its decoded claims.

    Uses a global in-memory JWKS cache that is refreshed every hour.
    """
    from jwt import get_unverified_header

    headers = get_unverified_header(token)
    kid = headers.get("kid")
    if not kid:
        raise jwt.InvalidTokenError("Missing kid in token header")

    try:
        jwks = await _fetch_clerk_jwks(settings)
    except httpx.HTTPError as exc:
        raise jwt.InvalidTokenError(f"Failed to fetch JWKS: {exc}") from exc

    jwk_dict = jwks.get(kid)
    if not jwk_dict:
        raise jwt.InvalidTokenError(f"No JWK found for kid={kid}")

    public_key = RSAAlgorithm.from_jwk(jwk_dict)
    payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        options={"verify_exp": True},
    )
    return payload
