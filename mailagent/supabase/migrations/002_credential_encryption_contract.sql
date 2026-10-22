-- New account credentials are stored as:
-- {"version": 1, "ciphertext": "<base64url AES-256-GCM payload>"}
--
-- Existing plaintext rows must be migrated by an approved, separately tested
-- operational procedure before the compatibility reader is enabled.
COMMENT ON COLUMN email_accounts.credentials IS
    'Versioned AES-256-GCM envelope; plaintext credentials are not accepted by the application.';
