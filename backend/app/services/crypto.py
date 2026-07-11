"""Encryption for provider tokens at rest.

OAuth access/refresh tokens are long-lived credentials that let us act on a
user's behalf (send Gmail, post to Discord/Slack). They must never be stored in
plaintext. This module wraps Fernet (AES-128-CBC + HMAC) symmetric encryption so
the token-store service can transparently encrypt on write and decrypt on read.

The key comes from ``settings.token_encryption_key``. For local dev, if unset, a
stable key is derived from ``jwt_secret`` so the app runs out-of-the-box — but in
production you MUST set an explicit ``SENTINEL_TOKEN_ENCRYPTION_KEY`` (generate
one with ``Fernet.generate_key()``), otherwise rotating the JWT secret would make
all stored tokens undecryptable.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class TokenCryptoError(RuntimeError):
    """Raised when a token cannot be decrypted (wrong/rotated key or tampering)."""


@lru_cache
def _fernet() -> Fernet:
    key = settings.token_encryption_key.strip()
    if key:
        # Accept a raw urlsafe-base64 Fernet key as provided.
        return Fernet(key.encode("utf-8"))
    # Dev fallback: derive a deterministic 32-byte key from the JWT secret.
    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    derived = base64.urlsafe_b64encode(digest)
    return Fernet(derived)


def encrypt(plaintext: str) -> str:
    """Encrypt a token string, returning urlsafe ciphertext for DB storage."""
    if plaintext is None:
        raise TokenCryptoError("Cannot encrypt None.")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored token; raises ``TokenCryptoError`` if it can't be read."""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise TokenCryptoError("Failed to decrypt token (bad key or data).") from exc
