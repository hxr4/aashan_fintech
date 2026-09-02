# Deploying to Supabase

Order matters, and two things commonly go wrong.

**`:'app_password'` is psql syntax.** The Supabase SQL Editor is not psql, so
Postgres receives the literal text and raises a syntax error -- which rolls the
whole script back, creating nothing. Use a literal password.

**`GRANT ... ON ALL TABLES` only covers tables that already exist.** Granting
before the migrations run grants on an empty schema. Migrate first, then grant.

1. `DATABASE_URL='<admin connection>' .venv/bin/python scripts/migrate.py`
2. Paste `supabase_role_setup.sql` into the SQL Editor, with a real password
3. `ADMIN_DATABASE_URL=... APP_DATABASE_URL=... .venv/bin/python scripts/verify_rls.py`

Step 3 is the one that settles it. Everything else is a claim.

## Connecting as a custom role

Prefer the **direct connection** with the plain role name:

    postgresql://aashan_app:<password>@db.<project-ref>.supabase.co:5432/postgres

Supavisor, the pooler, expects `<role>.<project-ref>` as the username and is
known to answer "Tenant or user not found" for custom roles. If you must use the
pooler, try `aashan_app.<project-ref>`; if that is refused, use the direct
connection. Newer projects serve the direct host over IPv6 only, so an IPv4-only
network may need the pooler or the IPv4 add-on.

# Deploying the application role

RLS only protects you if the application connects as a role that does **not**
own the tables and does **not** hold BYPASSRLS. Running migrations as the same
role you serve traffic with defeats the whole mechanism.

Run migrations as an owner/admin role, then serve traffic as `aashan_app`:

```sql
CREATE ROLE aashan_app LOGIN PASSWORD :'app_password' NOBYPASSRLS;

GRANT USAGE ON SCHEMA public, auth TO aashan_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aashan_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aashan_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aashan_app;

-- No DDL, and explicitly not the table owner.
REVOKE CREATE ON SCHEMA public FROM aashan_app;
```

Then point `DATABASE_URL` at `aashan_app`, and keep the migration credentials
somewhere the running service cannot read.

On Supabase specifically: do **not** use the service-role connection string for
`DATABASE_URL`. It bypasses RLS by design, and every policy here becomes
decoration.

## Verified behaviour (PostgreSQL 16)

Two users hold data. User A asks for their transactions. Rows each connection
can see, measured before and after migration 005:

| connection role                      | without 005 | with 005 |
|--------------------------------------|-------------|----------|
| superuser / service-role key         | 2 of 2      | **2 of 2** |
| table owner (the role that migrates) | 2 of 2      | 1 of 2   |
| non-owning app role                  | 1 of 2      | 1 of 2   |

Read the first row carefully. `FORCE ROW LEVEL SECURITY` fixes the table-owner
case and does **nothing** for a superuser, because a superuser bypasses RLS by
definition. There is no migration that can fix that one -- it is a deployment
choice. Using Supabase's service-role connection string as `DATABASE_URL`
defeats every policy in this directory.

Attempting to write a row owned by another user is refused in all cases.

Verify after deploying — this must return `t` for every row:

```sql
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class WHERE relname IN ('transactions', 'source_observations');
```
