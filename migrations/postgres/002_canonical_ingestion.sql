ALTER TABLE transactions ADD COLUMN IF NOT EXISTS value_date TIMESTAMPTZ;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS mode TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS transaction_type TEXT NOT NULL DEFAULT 'DEBIT';
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS transaction_status TEXT NOT NULL DEFAULT 'CONFIRMED';
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS merchant_candidate TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS merchant_confidence NUMERIC(5, 4);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS duplicate_status TEXT NOT NULL DEFAULT 'NOT_DUPLICATE';
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS transfer_status TEXT NOT NULL DEFAULT 'NOT_TRANSFER';
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS budget_status TEXT NOT NULL DEFAULT 'UNDECIDED';

ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS value_date TIMESTAMPTZ;
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS transaction_type TEXT NOT NULL DEFAULT 'DEBIT';
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS category_candidate TEXT;
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS transaction_status TEXT NOT NULL DEFAULT 'CONFIRMED';
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS merchant_candidate TEXT;
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS merchant_confidence NUMERIC(5, 4);
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS duplicate_status TEXT NOT NULL DEFAULT 'NOT_DUPLICATE';
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS transfer_status TEXT NOT NULL DEFAULT 'NOT_TRANSFER';
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS budget_status TEXT NOT NULL DEFAULT 'UNDECIDED';
ALTER TABLE transaction_candidates ADD COLUMN IF NOT EXISTS external_id TEXT;

ALTER TABLE merchant_rules ADD COLUMN IF NOT EXISTS category_name TEXT;

ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_direction_check;
ALTER TABLE transactions ADD CONSTRAINT transactions_direction_check CHECK (direction IN ('CREDIT', 'DEBIT', 'TRANSFER'));
ALTER TABLE transaction_candidates DROP CONSTRAINT IF EXISTS transaction_candidates_direction_check;
ALTER TABLE transaction_candidates ADD CONSTRAINT transaction_candidates_direction_check CHECK (direction IN ('CREDIT', 'DEBIT', 'TRANSFER'));

CREATE INDEX IF NOT EXISTS idx_transactions_external_owner ON transactions(user_id, source, external_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_external_id ON transactions(user_id, source, external_id) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_candidates_external_owner ON transaction_candidates(user_id, source, external_id);
CREATE INDEX IF NOT EXISTS idx_candidates_review_owner ON transaction_candidates(user_id, review_status);
