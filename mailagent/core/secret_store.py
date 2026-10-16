"""Authenticated encryption for BYOK credentials.

The encryption key is supplied by an environment/KMS integration and is never
returned to callers. Ciphertext is safe to persist in Postgres.
"""

import base64
import os
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretStore:
    def __init__(self, key: Optional[bytes] = None) -> None:
        raw_key = key or self._key_from_environment()
        if len(raw_key) not in {16, 24, 32}:
            raise ValueError("MAILAGENT_ENCRYPTION_KEY must be 128, 192, or 256 bits")
        self._key = raw_key

    @staticmethod
    def _key_from_environment() -> bytes:
        encoded = os.environ.get("MAILAGENT_ENCRYPTION_KEY", "")
        if not encoded:
            raise ValueError("MAILAGENT_ENCRYPTION_KEY is required")
        try:
            return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        except ValueError as exc:
            raise ValueError("MAILAGENT_ENCRYPTION_KEY must be base64url encoded") from exc

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise ValueError("cannot encrypt an empty secret")
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._key).encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            payload = base64.urlsafe_b64decode(token.encode("ascii"))
            plaintext = AESGCM(self._key).decrypt(payload[:12], payload[12:], None)
            return plaintext.decode("utf-8")
        except (InvalidTag, ValueError, TypeError) as exc:
            raise ValueError("invalid encrypted secret") from exc

    @staticmethod
    def redacted(secret: str) -> str:
        if len(secret) < 4:
            return "••••"
        return f"••••{secret[-4:]}"
