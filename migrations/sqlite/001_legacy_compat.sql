CREATE TABLE IF NOT EXISTS aggregate_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    source TEXT NOT NULL DEFAULT 'LEGACY',
    import_id TEXT
);

CREATE TABLE IF NOT EXISTS budgets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount >= 0),
    period_start TEXT,
    period_end TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, category)
);

CREATE TABLE IF NOT EXISTS aa_consent_context (
    consent_id TEXT PRIMARY KEY,
    data_range_from TEXT NOT NULL,
    data_range_to TEXT NOT NULL,
    auto_fetch INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    provider TEXT NOT NULL DEFAULT 'SETU',
    purpose_json TEXT,
    connection_id TEXT
);

CREATE TABLE IF NOT EXISTS aa_webhook_events (
    event_key TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    consent_id TEXT,
    session_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS aa_processed_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
