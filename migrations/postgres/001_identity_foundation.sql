CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY,
    display_name TEXT,
    preferred_currency TEXT NOT NULL DEFAULT 'INR',
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    locale TEXT NOT NULL DEFAULT 'en-IN',
    notification_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    onboarding_state TEXT NOT NULL DEFAULT 'NOT_STARTED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID,
    identifier TEXT,
    name TEXT NOT NULL,
    kind TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('SETU', 'PDF', 'SMS', 'CSV', 'MANUAL')),
    provider TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACTIVE', 'PAUSED', 'FAILED', 'DISCONNECTED', 'EXPIRED')),
    institution_id UUID REFERENCES institutions(id) ON DELETE SET NULL,
    last_synchronized_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS financial_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    institution_id UUID REFERENCES institutions(id) ON DELETE SET NULL,
    connection_id UUID REFERENCES account_connections(id) ON DELETE SET NULL,
    account_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    masked_identifier TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    connection_status TEXT NOT NULL DEFAULT 'PENDING',
    last_synchronized_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    connection_id UUID REFERENCES account_connections(id) ON DELETE SET NULL,
    account_id UUID REFERENCES financial_accounts(id) ON DELETE SET NULL,
    provider TEXT NOT NULL,
    provider_consent_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    data_range_from TIMESTAMPTZ,
    data_range_to TIMESTAMPTZ,
    purpose JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, provider, provider_consent_id)
);

CREATE TABLE IF NOT EXISTS imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('CSV', 'PDF', 'SMS', 'SETU', 'MANUAL')),
    account_id UUID REFERENCES financial_accounts(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    filename TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT,
    error_category TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, source, idempotency_key)
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    import_id UUID REFERENCES imports(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_category TEXT,
    error_message TEXT,
    progress JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    system_key TEXT,
    name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS merchant_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    merchant_pattern TEXT NOT NULL,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transaction_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    account_id UUID REFERENCES financial_accounts(id) ON DELETE SET NULL,
    import_id UUID REFERENCES imports(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_record_id TEXT,
    transaction_at TIMESTAMPTZ,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    direction TEXT NOT NULL CHECK (direction IN ('CREDIT', 'DEBIT')),
    description TEXT,
    mode TEXT,
    classification_status TEXT NOT NULL DEFAULT 'PENDING',
    review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    account_id UUID REFERENCES financial_accounts(id) ON DELETE SET NULL,
    import_id UUID REFERENCES imports(id) ON DELETE SET NULL,
    source TEXT NOT NULL,
    source_record_id TEXT,
    external_id TEXT,
    transaction_at TIMESTAMPTZ NOT NULL,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    direction TEXT NOT NULL CHECK (direction IN ('CREDIT', 'DEBIT')),
    description TEXT,
    merchant_id TEXT,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    category_name TEXT,
    classification_method TEXT,
    classification_confidence NUMERIC(5, 4),
    classification_status TEXT NOT NULL DEFAULT 'CLASSIFIED',
    status TEXT NOT NULL DEFAULT 'CONFIRMED',
    budget_inclusion TEXT NOT NULL DEFAULT 'UNDECIDED' CHECK (budget_inclusion IN ('UNDECIDED', 'INCLUDED', 'EXCLUDED')),
    is_transfer BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transaction_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    transaction_id UUID REFERENCES transactions(id) ON DELETE CASCADE,
    candidate_id UUID REFERENCES transaction_candidates(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    changes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    category TEXT NOT NULL,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount >= 0),
    period_start DATE,
    period_end DATE,
    currency TEXT NOT NULL DEFAULT 'INR',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, category)
);

CREATE TABLE IF NOT EXISTS budget_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    category_name TEXT NOT NULL,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount >= 0),
    UNIQUE(budget_id, category_name)
);

CREATE TABLE IF NOT EXISTS aggregate_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    import_id UUID REFERENCES imports(id) ON DELETE SET NULL,
    source TEXT NOT NULL DEFAULT 'PIPELINE',
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS privacy_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_aggregate_snapshots_user_created ON aggregate_snapshots(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_imports_user_created ON imports(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON processing_jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidates_user_status ON transaction_candidates(user_id, review_status);
CREATE INDEX IF NOT EXISTS idx_audit_user_created ON audit_events(user_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_setu_webhook_once ON audit_events(entity_type, entity_id) WHERE entity_type = 'SETU_WEBHOOK';

-- STATEMENT BREAK --
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE merchant_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaction_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaction_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE aggregate_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE privacy_events ENABLE ROW LEVEL SECURITY;

-- STATEMENT BREAK --
CREATE POLICY profiles_owner ON profiles USING (id = auth.uid()) WITH CHECK (id = auth.uid());
CREATE POLICY institutions_owner_or_global ON institutions USING (owner_user_id IS NULL OR owner_user_id = auth.uid()) WITH CHECK (owner_user_id IS NULL OR owner_user_id = auth.uid());
CREATE POLICY account_connections_owner ON account_connections USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY financial_accounts_owner ON financial_accounts USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY consents_owner ON consents USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY imports_owner ON imports USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY processing_jobs_owner ON processing_jobs USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY categories_owner_or_global ON categories USING (user_id IS NULL OR user_id = auth.uid()) WITH CHECK (user_id IS NULL OR user_id = auth.uid());
CREATE POLICY merchant_rules_owner ON merchant_rules USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY transaction_candidates_owner ON transaction_candidates USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY transactions_owner ON transactions USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY transaction_reviews_owner ON transaction_reviews USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY budgets_owner ON budgets USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY budget_categories_owner ON budget_categories USING (EXISTS (SELECT 1 FROM budgets WHERE budgets.id = budget_categories.budget_id AND budgets.user_id = auth.uid())) WITH CHECK (EXISTS (SELECT 1 FROM budgets WHERE budgets.id = budget_categories.budget_id AND budgets.user_id = auth.uid()));
CREATE POLICY aggregate_snapshots_owner ON aggregate_snapshots USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY audit_events_owner ON audit_events USING (user_id IS NULL OR user_id = auth.uid()) WITH CHECK (user_id IS NULL OR user_id = auth.uid());
CREATE POLICY privacy_events_owner ON privacy_events USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
