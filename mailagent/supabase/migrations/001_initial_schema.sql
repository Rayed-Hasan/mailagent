-- MailAgent Database Schema for Supabase

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    autonomy_mode VARCHAR(20) DEFAULT 'approve' CHECK (autonomy_mode IN ('approve', 'auto_safe', 'auto_full')),
    confidence_threshold FLOAT DEFAULT 0.85,
    max_auto_replies_per_hour INT DEFAULT 10,
    is_active BOOLEAN DEFAULT TRUE
);

-- Email accounts table
CREATE TABLE email_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('gmail', 'yahoo', 'imap')),
    email_address VARCHAR(255) NOT NULL,
    credentials JSONB NOT NULL, -- OAuth tokens or IMAP credentials
    is_active BOOLEAN DEFAULT TRUE,
    last_synced_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, email_address)
);

-- Emails table
CREATE TABLE emails (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES email_accounts(id) ON DELETE CASCADE,
    message_id VARCHAR(500) UNIQUE NOT NULL,
    thread_id VARCHAR(500),
    sender VARCHAR(255),
    sender_email VARCHAR(255),
    subject TEXT,
    body TEXT,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    raw_headers JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Classifications table
CREATE TABLE classifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id UUID REFERENCES emails(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL CHECK (category IN ('meets_reply', 'FYI', 'newsletter', 'promo', 'received', 'notification', 'spam', 'personal', 'urgent', 'sensitive')),
    priority_score INT CHECK (priority_score >= 0 AND priority_score <= 100),
    action VARCHAR(50) CHECK (action IN ('reply', 'draft_only', 'archive', 'flag_human')),
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(email_id)
);

-- Drafts table
CREATE TABLE drafts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id UUID REFERENCES emails(id) ON DELETE CASCADE,
    classification_id UUID REFERENCES classifications(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'sent', 'cancelled')),
    scheduled_send_at TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit log table
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id UUID REFERENCES emails(id) ON DELETE CASCADE,
    classification_id UUID REFERENCES classifications(id) ON DELETE SET NULL,
    draft_id UUID REFERENCES drafts(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL,
    category VARCHAR(50),
    action VARCHAR(50),
    reason TEXT,
    confidence FLOAT,
    context JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User voice profile table
CREATE TABLE user_voice_profile (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tone VARCHAR(100),
    avg_length INT,
    greeting_style TEXT,
    sign_off TEXT,
    common_phrases JSONB,
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Rate limits table
CREATE TABLE rate_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES email_accounts(id) ON DELETE CASCADE,
    hour_window TIMESTAMP WITH TIME ZONE NOT NULL,
    auto_replies_sent INT DEFAULT 0,
    last_reply_thread_id VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(account_id, hour_window)
);

-- Kill switch table
CREATE TABLE kill_switch (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    is_active BOOLEAN DEFAULT FALSE,
    reason TEXT,
    activated_at TIMESTAMP WITH TIME ZONE,
    activated_by VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_emails_account_id ON emails(account_id);
CREATE INDEX idx_emails_thread_id ON emails(thread_id);
CREATE INDEX idx_emails_received_at ON emails(received_at DESC);
CREATE INDEX idx_classifications_email_id ON classifications(email_id);
CREATE INDEX idx_classifications_category ON classifications(category);
CREATE INDEX idx_classifications_priority ON classifications(priority_score DESC);
CREATE INDEX idx_drafts_email_id ON drafts(email_id);
CREATE INDEX idx_drafts_status ON drafts(status);
CREATE INDEX idx_audit_log_email_id ON audit_log(email_id);
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_rate_limits_account_id ON rate_limits(account_id);
CREATE INDEX idx_rate_limits_hour_window ON rate_limits(hour_window);

-- Row Level Security (RLS) policies
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE emails ENABLE ROW LEVEL SECURITY;
ALTER TABLE classifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_voice_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE kill_switch ENABLE ROW LEVEL SECURITY;

-- Default policies (admin/service role can bypass with service role key)
-- These will be refined in production with proper user authentication
