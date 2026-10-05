"""Symmetric secret encryption (Fernet) for values stored at rest.

Used for per-user AI provider API keys. The key-encryption-key is derived from
``settings.jwt_secret`` so it never lives in the database. Values round-trip via
:func:`encrypt_secret` / :func:`decrypt_secret`; decryption failures return
``None`` rather than raising so callers can degrade gracefully.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from core.config import get_settings


def fernet() -> Fernet:
    """Return a :class:`Fernet` keyed from the application JWT secret."""
    settings = get_settings()
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    """Encrypt *value* and return the ciphertext as a string."""
    return fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str | None) -> str | None:
    """Decrypt *token* back to plaintext, or ``None`` if it is invalid/empty."""
    if not token:
        return None
    try:
        return fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


__all__ = ["fernet", "encrypt_secret", "decrypt_secret"]
