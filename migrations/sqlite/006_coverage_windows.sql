CREATE TABLE IF NOT EXISTS coverage_windows (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    account_id TEXT,
    source TEXT NOT NULL,
    covered_from TEXT NOT NULL,
    covered_to TEXT NOT NULL,
    completeness TEXT NOT NULL DEFAULT 'DECLARED',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, account_id, source, covered_from, covered_to)
);

CREATE INDEX IF NOT EXISTS idx_coverage_owner ON coverage_windows(user_id, source, covered_from);
