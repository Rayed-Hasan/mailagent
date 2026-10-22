-- Provider settings table for BYOK configuration
-- API keys are encrypted with AES-256-GCM using SecretStore
-- Format: {"version": 1, "ciphertext": "<base64url AES-256-GCM payload>"}

CREATE TABLE provider_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('claude', 'openai', 'google', 'ollama')),
    api_key JSONB NOT NULL, -- Encrypted API key
    model_classification VARCHAR(100) DEFAULT '',
    model_drafting VARCHAR(100) DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- Indexes for performance
CREATE INDEX idx_provider_settings_user_id ON provider_settings(user_id);
CREATE INDEX idx_provider_settings_provider ON provider_settings(provider);

-- Row Level Security
ALTER TABLE provider_settings ENABLE ROW LEVEL SECURITY;

-- RLS policy: Users can only see their own provider settings
CREATE POLICY "Users can view own provider settings"
    ON provider_settings FOR SELECT
    USING (user_id = auth.uid());

-- RLS policy: Users can insert their own provider settings
CREATE POLICY "Users can insert own provider settings"
    ON provider_settings FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- RLS policy: Users can update their own provider settings
CREATE POLICY "Users can update own provider settings"
    ON provider_settings FOR UPDATE
    USING (user_id = auth.uid());

-- RLS policy: Users can delete their own provider settings
CREATE POLICY "Users can delete own provider settings"
    ON provider_settings FOR DELETE
    USING (user_id = auth.uid());

-- Service role bypass for worker operations
COMMENT ON TABLE provider_settings IS
    'BYOK provider configuration with encrypted API keys; per-user isolation enforced by RLS';
COMMENT ON COLUMN provider_settings.api_key IS
    'Versioned AES-256-GCM envelope containing the provider API key';
