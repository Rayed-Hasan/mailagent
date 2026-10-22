-- Email labels table for automatic categorization
-- Labels are applied by the system based on classification results
-- User-created labels are distinguished by source='user'

CREATE TABLE email_labels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id UUID REFERENCES emails(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    source VARCHAR(20) DEFAULT 'system' CHECK (source IN ('system', 'user')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(email_id, name)
);

-- Indexes for performance
CREATE INDEX idx_email_labels_email_id ON email_labels(email_id);
CREATE INDEX idx_email_labels_name ON email_labels(name);

-- Row Level Security
ALTER TABLE email_labels ENABLE ROW LEVEL SECURITY;

-- RLS policy: Users can view labels for their own emails
CREATE POLICY "Users can view own email labels"
    ON email_labels FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM emails
            JOIN email_accounts ON emails.account_id = email_accounts.id
            WHERE emails.id = email_labels.email_id
            AND email_accounts.user_id = auth.uid()
        )
    );

-- RLS policy: Users can insert labels for their own emails
CREATE POLICY "Users can insert own email labels"
    ON email_labels FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM emails
            JOIN email_accounts ON emails.account_id = email_accounts.id
            WHERE emails.id = email_labels.email_id
            AND email_accounts.user_id = auth.uid()
        )
    );

-- RLS policy: Users can delete labels for their own emails
CREATE POLICY "Users can delete own email labels"
    ON email_labels FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM emails
            JOIN email_accounts ON emails.account_id = email_accounts.id
            WHERE emails.id = email_labels.email_id
            AND email_accounts.user_id = auth.uid()
        )
    );

COMMENT ON TABLE email_labels IS
    'Automatic and user-created email labels with source tracking and deduplication';
