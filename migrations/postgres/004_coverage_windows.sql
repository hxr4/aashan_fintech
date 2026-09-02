CREATE TABLE IF NOT EXISTS coverage_windows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    account_id UUID REFERENCES financial_accounts(id) ON DELETE SET NULL,
    source TEXT NOT NULL,
    covered_from DATE NOT NULL,
    covered_to DATE NOT NULL,
    completeness TEXT NOT NULL DEFAULT 'DECLARED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, account_id, source, covered_from, covered_to)
);

CREATE INDEX IF NOT EXISTS idx_coverage_owner ON coverage_windows(user_id, source, covered_from);

ALTER TABLE coverage_windows ENABLE ROW LEVEL SECURITY;
CREATE POLICY coverage_windows_owner ON coverage_windows
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
