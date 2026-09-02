CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT,
    preferred_currency TEXT NOT NULL DEFAULT 'INR',
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    locale TEXT NOT NULL DEFAULT 'en-IN',
    notification_preferences TEXT NOT NULL DEFAULT '{}',
    onboarding_state TEXT NOT NULL DEFAULT 'NOT_STARTED',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS institutions (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT,
    identifier TEXT,
    name TEXT NOT NULL,
    kind TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS account_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source TEXT NOT NULL,
    provider TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    institution_id TEXT,
    last_synchronized_at TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS financial_accounts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    institution_id TEXT,
    connection_id TEXT,
    account_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    masked_identifier TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    connection_status TEXT NOT NULL DEFAULT 'PENDING',
    last_synchronized_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS imports (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source TEXT NOT NULL,
    account_id TEXT,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    filename TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT,
    error_category TEXT,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, source, idempotency_key)
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    import_id TEXT,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_category TEXT,
    error_message TEXT,
    progress TEXT NOT NULL DEFAULT '{}',
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    system_key TEXT,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS merchant_rules (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    merchant_pattern TEXT NOT NULL,
    category_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction_candidates (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    account_id TEXT,
    import_id TEXT,
    source TEXT NOT NULL,
    source_record_id TEXT,
    transaction_at TEXT,
    amount REAL NOT NULL CHECK(amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    direction TEXT NOT NULL,
    description TEXT,
    mode TEXT,
    classification_status TEXT NOT NULL DEFAULT 'PENDING',
    review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    account_id TEXT,
    import_id TEXT,
    source TEXT NOT NULL,
    source_record_id TEXT,
    external_id TEXT,
    transaction_at TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    direction TEXT NOT NULL,
    mode TEXT,
    description TEXT,
    merchant_id TEXT,
    category_id TEXT,
    category_name TEXT,
    classification_method TEXT,
    classification_confidence REAL,
    classification_status TEXT NOT NULL DEFAULT 'CLASSIFIED',
    status TEXT NOT NULL DEFAULT 'CONFIRMED',
    budget_inclusion TEXT NOT NULL DEFAULT 'UNDECIDED',
    is_transfer INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction_reviews (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    transaction_id TEXT,
    candidate_id TEXT,
    action TEXT NOT NULL,
    changes TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS budget_categories (
    id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL,
    category_id TEXT,
    category_name TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount >= 0),
    UNIQUE(budget_id, category_name)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS privacy_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_aggregate_snapshots_user_created ON aggregate_snapshots(user_id, id);
CREATE INDEX IF NOT EXISTS idx_imports_user_created ON imports(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON processing_jobs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_at);
CREATE INDEX IF NOT EXISTS idx_candidates_user_status ON transaction_candidates(user_id, review_status);
CREATE INDEX IF NOT EXISTS idx_audit_user_created ON audit_events(user_id, created_at);
