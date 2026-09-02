-- Run this in the Supabase SQL Editor *after* scripts/migrate.py has created
-- the tables. Order matters: GRANT ... ON ALL TABLES only affects tables that
-- exist at the moment it runs, so granting first grants on nothing.
--
-- Replace the password below with a real one before running. Do not use
-- :'app_password' -- that is psql client-side syntax and the Supabase SQL
-- Editor is not psql, so Postgres sees it as a syntax error and the whole
-- script rolls back.

-- 1. The role the application connects as. Not a superuser, does not bypass
--    RLS, and does not own the tables -- all three matter.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aashan_app') THEN
        CREATE ROLE aashan_app LOGIN NOSUPERUSER NOBYPASSRLS
            PASSWORD 'REPLACE_WITH_A_REAL_PASSWORD';
    ELSE
        ALTER ROLE aashan_app LOGIN NOSUPERUSER NOBYPASSRLS
            PASSWORD 'REPLACE_WITH_A_REAL_PASSWORD';
    END IF;
END
$$;

-- 2. Data access, but no schema changes.
GRANT USAGE ON SCHEMA public TO aashan_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aashan_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aashan_app;

-- Tables created by future migrations are covered automatically.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aashan_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO aashan_app;

REVOKE CREATE ON SCHEMA public FROM aashan_app;

-- 3. Every policy calls auth.uid(), so the role has to be able to reach it.
--    Missing this makes every query fail with "permission denied for schema auth"
--    rather than with anything that points at the real cause.
GRANT USAGE ON SCHEMA auth TO aashan_app;
GRANT EXECUTE ON FUNCTION auth.uid() TO aashan_app;

-- 4. Confirm. rolsuper and rolbypassrls must both be false, or none of the
--    policies apply to this connection.
SELECT rolname, rolcanlogin, rolsuper, rolbypassrls
FROM pg_roles WHERE rolname = 'aashan_app';

-- 5. Confirm FORCE is set. Both columns must be true on every row.
SELECT relname, relrowsecurity AS rls_enabled, relforcerowsecurity AS rls_forced
FROM pg_class
WHERE relname IN ('transactions', 'source_observations', 'coverage_windows', 'budgets')
ORDER BY relname;
