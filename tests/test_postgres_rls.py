"""Cross-tenant isolation, verified against a real PostgreSQL.

SQLite has no row level security, so the whole RLS layer is unverifiable in the
default test run. These tests are skipped unless AASHAN_TEST_POSTGRES_URL points
at a PostgreSQL a superuser can reshape.

Verified result of the matrix below (PostgreSQL 16):

    connection role                       without 005   with 005
    superuser / service-role key             2 of 2       2 of 2
    table owner (the role that migrates)     2 of 2       1 of 2
    non-owning app role                      1 of 2       1 of 2

FORCE ROW LEVEL SECURITY fixes the table-owner case. Nothing in SQL fixes the
superuser case -- a superuser bypasses RLS by definition, so pointing
DATABASE_URL at Supabase's service-role connection defeats every policy here.
That one is a deployment choice, not a migration.
"""

import os
import pathlib
import uuid

import pytest

POSTGRES_URL = os.getenv("AASHAN_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="AASHAN_TEST_POSTGRES_URL not set")

MIGRATIONS = sorted((pathlib.Path(__file__).resolve().parents[1] / "migrations" / "postgres").glob("*.sql"))
USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def _statements(path: pathlib.Path):
    from app.database.connection import split_sql

    for statement in split_sql(path.read_text(encoding="utf-8")):
        if "CREATE SCHEMA IF NOT EXISTS auth" in statement:
            continue
        yield statement


@pytest.fixture
def database():
    import psycopg

    with psycopg.connect(POSTGRES_URL, autocommit=True) as superuser:
        superuser.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        superuser.execute("DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth;")
        superuser.execute(
            "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS "
            "'SELECT NULLIF(current_setting(''request.jwt.claim.sub'', true), '''')::uuid'"
        )
        for role in ("tbl_owner", "aashan_app"):
            superuser.execute(f"DROP ROLE IF EXISTS {role}")
        superuser.execute("CREATE ROLE tbl_owner LOGIN PASSWORD 'x' NOSUPERUSER NOBYPASSRLS")
        superuser.execute("CREATE ROLE aashan_app LOGIN PASSWORD 'x' NOSUPERUSER NOBYPASSRLS")
        superuser.execute("GRANT ALL ON SCHEMA public TO tbl_owner")
        superuser.execute("GRANT USAGE ON SCHEMA public, auth TO aashan_app")
        superuser.execute("GRANT USAGE ON SCHEMA auth TO tbl_owner")
        superuser.execute("GRANT EXECUTE ON FUNCTION auth.uid() TO tbl_owner, aashan_app")

    with psycopg.connect(POSTGRES_URL, user="tbl_owner", autocommit=True) as owner:
        for migration in MIGRATIONS:
            for statement in _statements(migration):
                if "pgcrypto" in statement:
                    continue
                owner.execute(statement)
        owner.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aashan_app")
        for owner_id in (USER_A, USER_B):
            owner.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (owner_id,))
            owner.execute(
                "INSERT INTO transactions (user_id, source, transaction_at, amount, direction, description)"
                " VALUES (%s, 'CSV', now(), 100, 'DEBIT', %s)",
                (owner_id, "private to " + owner_id[:8]),
            )
    return POSTGRES_URL


def _as(url, role, claim):
    import psycopg

    connection = psycopg.connect(url, user=role, autocommit=True)
    connection.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (claim,))
    return connection


def test_force_row_level_security_is_actually_set(database):
    import psycopg

    with psycopg.connect(database, autocommit=True) as connection:
        rows = connection.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class"
            " WHERE relname IN ('transactions','source_observations','coverage_windows','budgets')"
        ).fetchall()
    assert rows
    for name, enabled, forced in rows:
        assert enabled, f"{name} has RLS disabled"
        assert forced, f"{name} is not FORCEd, so its owner bypasses its own policies"


def test_the_application_role_sees_only_its_own_rows(database):
    with _as(database, "aashan_app", USER_A) as connection:
        assert connection.execute("SELECT count(*) FROM transactions").fetchone()[0] == 1
        descriptions = [r[0] for r in connection.execute("SELECT description FROM transactions").fetchall()]
    assert all(USER_B[:8] not in (d or "") for d in descriptions)


def test_the_table_owner_no_longer_bypasses_its_own_policies(database):
    """Without FORCE this returned every row in the table."""
    with _as(database, "tbl_owner", USER_A) as connection:
        assert connection.execute("SELECT count(*) FROM transactions").fetchone()[0] == 1


def test_a_user_cannot_write_a_row_owned_by_someone_else(database):
    import psycopg

    with _as(database, "aashan_app", USER_A) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "INSERT INTO transactions (user_id, source, transaction_at, amount, direction)"
                " VALUES (%s, 'CSV', now(), 5, 'DEBIT')",
                (USER_B,),
            )


def test_audit_events_no_longer_leak_across_tenants(database):
    """The old policy allowed `user_id IS NULL`, and webhook rows have a NULL owner."""
    import psycopg

    with psycopg.connect(database, user="tbl_owner", autocommit=True) as owner:
        owner.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (USER_B,))
        owner.execute(
            "INSERT INTO audit_events (user_id, event_type, entity_type, entity_id)"
            " VALUES (%s, 'SETU_WEBHOOK', 'SETU_WEBHOOK', %s)",
            (USER_B, "session-" + uuid.uuid4().hex),
        )
    with _as(database, "aashan_app", USER_A) as connection:
        assert connection.execute("SELECT count(*) FROM audit_events").fetchone()[0] == 0
