-- Simple owner-controlled auto-reply toggle. Disabled unless explicitly enabled.
CREATE TABLE IF NOT EXISTS automation_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    auto_reply_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE automation_settings ENABLE ROW LEVEL SECURITY;
