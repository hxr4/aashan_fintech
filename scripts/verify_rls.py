"""Prove cross-tenant isolation on the real database, not a local stand-in.

Reads two connection strings from the environment:

    ADMIN_DATABASE_URL   an admin/owner connection, used to seed two test users
    APP_DATABASE_URL     the connection the application will actually use

It writes two throwaway transactions belonging to two synthetic users, asks the
application connection what it can see, and deletes them again.

The check that matters most is the first one. A superuser or a BYPASSRLS role
ignores every policy in migrations/postgres/, and no migration can change that --
it is decided entirely by which role the application connects as.
"""

from __future__ import annotations

import os
import sys
import uuid
from urllib.parse import urlsplit

USER_A = "aaaaaaaa-0000-4000-8000-" + uuid.uuid4().hex[:12]
USER_B = "bbbbbbbb-0000-4000-8000-" + uuid.uuid4().hex[:12]

OWNED_TABLES = (
    "transactions", "source_observations", "coverage_windows", "budgets",
    "imports", "transaction_candidates", "aggregate_snapshots", "audit_events",
)


def describe(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.username}@{parts.hostname}"


def main() -> int:
    admin_url = os.getenv("ADMIN_DATABASE_URL", "")
    app_url = os.getenv("APP_DATABASE_URL", "")
    if not admin_url or not app_url:
        print("Set ADMIN_DATABASE_URL and APP_DATABASE_URL.", file=sys.stderr)
        return 2

    import psycopg

    failures: list[str] = []
    print(f"admin : {describe(admin_url)}")
    print(f"app   : {describe(app_url)}\n")

    # --- 1. what role does the application connect as? -----------------------
    with psycopg.connect(app_url, autocommit=True) as app:
        role, is_super, bypass = app.execute(
            "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
    print("1. Application connection role")
    print(f"     role          : {role}")
    print(f"     superuser     : {is_super}")
    print(f"     bypasses RLS  : {bypass}")
    if is_super or bypass:
        failures.append(
            f"the application connects as '{role}', which bypasses row level security entirely. "
            "Every policy in migrations/postgres/ is decoration for this connection."
        )
        print("     VERDICT       : FAIL - this role ignores all policies\n")
    else:
        print("     VERDICT       : ok\n")

    # --- 2. is FORCE actually set? ------------------------------------------
    print("2. FORCE ROW LEVEL SECURITY on owned tables")
    with psycopg.connect(admin_url, autocommit=True) as admin:
        rows = admin.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class"
            " WHERE relname = ANY(%s) ORDER BY relname", (list(OWNED_TABLES),)
        ).fetchall()
    if not rows:
        failures.append("none of the expected tables exist - have the migrations been applied?")
        print("     no tables found. Run scripts/migrate.py first.\n")
    for name, enabled, forced in rows:
        mark = "ok  " if (enabled and forced) else "FAIL"
        print(f"     {mark} {name:<24} enabled={enabled!s:<5} forced={forced}")
        if not (enabled and forced):
            failures.append(f"{name}: rls enabled={enabled} forced={forced}")
    print()

    # --- 3. can the app connection read another user's rows? ----------------
    print("3. Cross-tenant read")
    seeded = False
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            for owner in (USER_A, USER_B):
                admin.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (owner,))
                admin.execute(
                    "INSERT INTO transactions (user_id, source, transaction_at, amount, direction, description)"
                    " VALUES (%s, 'CSV', now(), 1.00, 'DEBIT', %s)",
                    (owner, "rls probe " + owner[:8]),
                )
            seeded = True

        with psycopg.connect(app_url, autocommit=True) as app:
            app.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (USER_A,))
            visible = app.execute(
                "SELECT count(*) FROM transactions WHERE description LIKE 'rls probe %%'"
            ).fetchone()[0]
            print(f"     asking as user A, probe rows visible: {visible} of 2")
            if visible != 1:
                failures.append(
                    f"the application connection sees {visible} of 2 probe rows; it must see exactly 1"
                )

            print("4. Cross-tenant write")
            try:
                app.execute(
                    "INSERT INTO transactions (user_id, source, transaction_at, amount, direction, description)"
                    " VALUES (%s, 'CSV', now(), 1.00, 'DEBIT', 'rls probe forged')",
                    (USER_B,),
                )
                failures.append("the application connection can write rows owned by another user")
                print("     writing a row owned by user B: ALLOWED - FAIL")
            except psycopg.Error:
                print("     writing a row owned by user B: blocked - ok")
    finally:
        if seeded:
            with psycopg.connect(admin_url, autocommit=True) as admin:
                admin.execute("DELETE FROM transactions WHERE description LIKE 'rls probe %'")

    print("\n" + "=" * 62)
    if failures:
        print(f"{len(failures)} PROBLEM(S):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("Cross-tenant isolation verified on this database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
