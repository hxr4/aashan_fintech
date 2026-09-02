CREATE INDEX IF NOT EXISTS idx_transactions_external_owner ON transactions(user_id, source, external_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_external_id ON transactions(user_id, source, external_id) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_candidates_external_owner ON transaction_candidates(user_id, source, external_id);
CREATE INDEX IF NOT EXISTS idx_imports_idempotency_owner ON imports(user_id, source, idempotency_key);
