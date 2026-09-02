-- Row Level Security was ENABLEd but never FORCEd, and the application role
-- creates these tables, so it owns them -- and a table owner is exempt from its
-- own RLS unless FORCE is set. Every policy in 001 was therefore decorative for
-- the one connection that matters. If DATABASE_URL points at a Supabase
-- service-role or `postgres` connection, RLS is bypassed outright.
--
-- Two things fix it: FORCE on every owned table, and connecting as a role that
-- does not own them (see the aashan_app role below).

-- Supabase supplies auth.uid(). Plain PostgreSQL does not, so the policies in
-- 001 cannot even be created there. This shim makes the schema portable and
-- deliberately does not overwrite a real implementation.
CREATE SCHEMA IF NOT EXISTS auth;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'auth' AND p.proname = 'uid'
    ) THEN
        EXECUTE $fn$
            CREATE FUNCTION auth.uid() RETURNS uuid
            LANGUAGE sql STABLE
            AS 'SELECT NULLIF(current_setting(''request.jwt.claim.sub'', true), '''')::uuid';
        $fn$;
    END IF;
END
$$;

DO $$
DECLARE
    owned_table text;
BEGIN
    FOREACH owned_table IN ARRAY ARRAY[
        'profiles', 'institutions', 'account_connections', 'financial_accounts',
        'consents', 'imports', 'processing_jobs', 'categories', 'merchant_rules',
        'transaction_candidates', 'transactions', 'transaction_reviews',
        'budgets', 'budget_categories', 'aggregate_snapshots', 'audit_events',
        'privacy_events', 'source_observations', 'coverage_windows'
    ]
    LOOP
        IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = owned_table) THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', owned_table);
            -- The line that was missing: without it the owner reads everything.
            EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', owned_table);
        END IF;
    END LOOP;
END
$$;

-- audit_events allowed `user_id IS NULL OR user_id = auth.uid()`, and webhook
-- audit rows are written with a NULL owner -- so every authenticated user could
-- read every other user's consent and session identifiers.
DROP POLICY IF EXISTS audit_events_owner ON audit_events;
CREATE POLICY audit_events_owner ON audit_events
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- System rows with no owner are written by a role that bypasses RLS, never read
-- through a user session.
DROP POLICY IF EXISTS institutions_owner_or_global ON institutions;
CREATE POLICY institutions_owner_or_global ON institutions
    USING (owner_user_id IS NULL OR owner_user_id = auth.uid())
    WITH CHECK (owner_user_id = auth.uid());

DROP POLICY IF EXISTS categories_owner_or_global ON categories;
CREATE POLICY categories_owner_or_global ON categories
    USING (user_id IS NULL OR user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());
