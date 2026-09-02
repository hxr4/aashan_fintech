CREATE TABLE IF NOT EXISTS consents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    connection_id TEXT,
    account_id TEXT,
    provider TEXT NOT NULL,
    provider_consent_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    data_range_from TEXT,
    data_range_to TEXT,
    purpose TEXT NOT NULL DEFAULT '{}',
    expires_at TEXT,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, provider, provider_consent_id)
);
