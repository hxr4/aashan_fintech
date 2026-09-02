CREATE TABLE IF NOT EXISTS source_observations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    transaction_id TEXT,
    candidate_id TEXT,
    import_id TEXT,
    source TEXT NOT NULL,
    provider TEXT,
    external_id TEXT,
    source_record_id TEXT,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    transaction_at TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    direction TEXT NOT NULL,
    description TEXT,
    mode TEXT,
    match_method TEXT NOT NULL DEFAULT 'NEW',
    match_score REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_observations_txn ON source_observations(user_id, transaction_id);
CREATE INDEX IF NOT EXISTS idx_observations_source ON source_observations(user_id, source);
CREATE INDEX IF NOT EXISTS idx_observations_external ON source_observations(user_id, external_id);
CREATE INDEX IF NOT EXISTS idx_transactions_content_hash ON transactions(user_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_transactions_match_window ON transactions(user_id, direction, amount, transaction_at);
