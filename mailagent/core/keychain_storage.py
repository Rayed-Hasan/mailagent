"""
OS keychain credential storage for secure credential management
"""

import keyring
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class KeychainStorage:
    """Secure credential storage using OS keychain"""

    SERVICE_NAME = "mailagent"

    @classmethod
    def scoped_key(cls, user_id: str, credential_type: str, name: str) -> str:
        """Return a non-secret, account-scoped keychain identifier."""
        if not user_id or not credential_type or not name:
            raise ValueError("credential scope values cannot be empty")
        return f"{user_id}:{credential_type}:{name}"

    @staticmethod
    def set_credential(key_name: str, value: str) -> bool:
        """
        Store a credential in the OS keychain.

        Args:
            key_name: Name/identifier for the credential
            value: The credential value to store

        Returns:
            True if successful, False otherwise
        """
        try:
            keyring.set_password(KeychainStorage.SERVICE_NAME, key_name, value)
            return True
        except Exception:
            logger.exception("Failed to store credential in keychain")
            return False

    @staticmethod
    def get_credential(key_name: str) -> Optional[str]:
        """
        Retrieve a credential from the OS keychain.

        Args:
            key_name: Name/identifier for the credential

        Returns:
            The credential value if found, None otherwise
        """
        try:
            value = keyring.get_password(KeychainStorage.SERVICE_NAME, key_name)
            return value
        except Exception:
            logger.exception("Failed to retrieve credential from keychain")
            return None

    @staticmethod
    def delete_credential(key_name: str) -> bool:
        """
        Delete a credential from the OS keychain.

        Args:
            key_name: Name/identifier for the credential

        Returns:
            True if successful, False otherwise
        """
        try:
            keyring.delete_password(KeychainStorage.SERVICE_NAME, key_name)
            return True
        except Exception:
            logger.exception("Failed to delete credential from keychain")
            return False

    @staticmethod
    def is_available() -> bool:
        """
        Check if keychain storage is available on this system.

        Returns:
            True if keychain is available, False otherwise
        """
        try:
            # Try a simple get/set operation to test availability
            test_key = "__mailagent_test__"
            keyring.set_password(KeychainStorage.SERVICE_NAME, test_key, "test")
            keyring.delete_password(KeychainStorage.SERVICE_NAME, test_key)
            return True
        except Exception:
            return False
