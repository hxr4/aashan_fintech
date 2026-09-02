CREATE TABLE IF NOT EXISTS source_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    transaction_id UUID REFERENCES transactions(id) ON DELETE CASCADE,
    candidate_id UUID REFERENCES transaction_candidates(id) ON DELETE SET NULL,
    import_id UUID REFERENCES imports(id) ON DELETE SET NULL,
    source TEXT NOT NULL,
    provider TEXT,
    external_id TEXT,
    source_record_id TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    transaction_at TIMESTAMPTZ NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    direction TEXT NOT NULL,
    description TEXT,
    mode TEXT,
    match_method TEXT NOT NULL DEFAULT 'NEW',
    match_score NUMERIC(5, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE transactions ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS content_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_observations_txn ON source_observations(user_id, transaction_id);
CREATE INDEX IF NOT EXISTS idx_observations_source ON source_observations(user_id, source);
CREATE INDEX IF NOT EXISTS idx_observations_external ON source_observations(user_id, external_id);
CREATE INDEX IF NOT EXISTS idx_transactions_content_hash ON transactions(user_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_transactions_match_window ON transactions(user_id, direction, amount, transaction_at);

-- The old key made the source part of identity, so the same purchase seen by
-- SMS and by a statement could never collide. Identity is the event, not the pipe.
DROP INDEX IF EXISTS uq_transactions_external_id;
CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_owner_external_id
    ON transactions(user_id, external_id) WHERE external_id IS NOT NULL;

ALTER TABLE source_observations ENABLE ROW LEVEL SECURITY;
CREATE POLICY source_observations_owner ON source_observations
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
