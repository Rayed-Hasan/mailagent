"""Authenticated encryption for BYOK credentials.

The encryption key is supplied by an environment/KMS integration and is never
returned to callers. Ciphertext is safe to persist in Postgres.
"""

import base64
import binascii
import os
import logging
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretStore:
    _KEYCHAIN_NAME = "encryption-key"

    def __init__(self, key: Optional[bytes] = None) -> None:
        raw_key = key or self._key_from_environment()
        if len(raw_key) != 32:
            raise ValueError("MAILAGENT_ENCRYPTION_KEY must be 256 bits")
        self._key = raw_key

    @staticmethod
    def _key_from_environment() -> bytes:
        encoded = os.environ.get("MAILAGENT_ENCRYPTION_KEY", "")
        if not encoded:
            from mailagent.core.keychain_storage import KeychainStorage
            encoded = KeychainStorage.get_credential(SecretStore._KEYCHAIN_NAME) or ""
            if not encoded:
                raw_key = os.urandom(32)
                encoded = base64.urlsafe_b64encode(raw_key).decode("ascii")
                if not KeychainStorage.set_credential(SecretStore._KEYCHAIN_NAME, encoded):
                    raise ValueError(
                        "MAILAGENT_ENCRYPTION_KEY is required when the OS keychain is unavailable"
                    )
        try:
            return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        except (ValueError, binascii.Error) as exc:
            raise ValueError("MAILAGENT_ENCRYPTION_KEY must be base64url encoded") from exc

    def encrypt(self, plaintext: str, associated_data: Optional[str] = None) -> str:
        if not plaintext:
            raise ValueError("cannot encrypt an empty secret")
        nonce = os.urandom(12)
        aad = associated_data.encode("utf-8") if associated_data else None
        ciphertext = AESGCM(self._key).encrypt(
            nonce, plaintext.encode("utf-8"), aad
        )
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, token: str, associated_data: Optional[str] = None) -> str:
        try:
            payload = base64.urlsafe_b64decode(token.encode("ascii"))
            if len(payload) < 28:
                raise ValueError("invalid encrypted secret")
            aad = associated_data.encode("utf-8") if associated_data else None
            plaintext = AESGCM(self._key).decrypt(payload[:12], payload[12:], aad)
            return plaintext.decode("utf-8")
        except (InvalidTag, ValueError, TypeError, UnicodeDecodeError, binascii.Error) as exc:
            raise ValueError("invalid encrypted secret") from exc

    @staticmethod
    def redacted(secret: str) -> str:
        if len(secret) < 4:
            return "••••"
        return f"••••{secret[-4:]}"
