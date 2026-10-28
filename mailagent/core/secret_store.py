"""Authenticated encryption for BYOK credentials.

The encryption key is supplied by an environment/KMS integration and is never
returned to callers. Ciphertext is safe to persist in Postgres.
"""

import base64
import binascii
import os
import re
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_BASE64URL_UNPADDED_KEY = re.compile(r"^[A-Za-z0-9_-]{43}$")
_BASE64URL_PADDED_KEY = re.compile(r"^[A-Za-z0-9_-]{43}=$")


def decode_encryption_key(encoded: str, *, allow_padding: bool = False) -> bytes:
    """Decode a 32-byte AES key from its canonical base64url representation."""
    valid = _BASE64URL_UNPADDED_KEY.fullmatch(encoded or "")
    if not valid and allow_padding:
        valid = _BASE64URL_PADDED_KEY.fullmatch(encoded or "")
    if not valid:
        raise ValueError(
            "MAILAGENT_ENCRYPTION_KEY must be a 43-character unpadded base64url encoding of 32 random bytes"
        )
    try:
        decoded = base64.b64decode(
            encoded.rstrip("=") + "=", altchars=b"-_", validate=True
        )
    except (ValueError, binascii.Error) as exc:
        raise ValueError(
            "MAILAGENT_ENCRYPTION_KEY must be a 43-character unpadded base64url encoding of 32 random bytes"
        ) from exc
    if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != encoded.rstrip("="):
        raise ValueError(
            "MAILAGENT_ENCRYPTION_KEY must be a 43-character unpadded base64url encoding of 32 random bytes"
        )
    return decoded


class SecretStore:
    _KEYCHAIN_NAME = "encryption-key"

    def __init__(self, key: Optional[bytes] = None) -> None:
        raw_key = key if key is not None else self._key_from_environment()
        if len(raw_key) != 32:
            raise ValueError("Encryption key must contain exactly 32 bytes (256 bits)")
        self._key = raw_key

    @staticmethod
    def _key_from_environment() -> bytes:
        encoded = os.environ.get("MAILAGENT_ENCRYPTION_KEY", "")
        if encoded:
            return decode_encryption_key(encoded)

        from mailagent.core.keychain_storage import KeychainStorage
        keychain_value = KeychainStorage.get_credential(SecretStore._KEYCHAIN_NAME) or ""
        if keychain_value:
            return decode_encryption_key(keychain_value, allow_padding=True)

        encoded = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        if not KeychainStorage.set_credential(SecretStore._KEYCHAIN_NAME, encoded):
            raise ValueError(
                "MAILAGENT_ENCRYPTION_KEY is required when the OS keychain is unavailable"
            )
        return decode_encryption_key(encoded, allow_padding=True)

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
