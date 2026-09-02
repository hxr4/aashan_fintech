"""Apply the PostgreSQL migrations to whatever DATABASE_URL points at.

Run this with an admin connection (Supabase's `postgres` role). The application
must NOT run as that role afterwards -- see migrations/postgres/README.md.

    DATABASE_URL='postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres' \
        .venv/bin/python scripts/migrate.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2
    if url.startswith("sqlite"):
        print("DATABASE_URL points at SQLite. Nothing to do.", file=sys.stderr)
        return 2

    # Show where we are going without ever printing the password.
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    print(f"target : {parts.username}@{parts.hostname}:{parts.port or 5432}{parts.path}")

    from app.config import settings

    settings.database_url = url

    from app.database.connection import run_postgres_migrations
    from sqlalchemy import create_engine, text

    engine = create_engine(url, pool_pre_ping=True, future=True)
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT current_user, usesuper FROM pg_user WHERE usename = current_user")).first()
        if row:
            print(f"running as : {row[0]} (superuser={row[1]})")
        before = connection.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar()
    engine.dispose()

    print("applying migrations ...")
    run_postgres_migrations()

    engine = create_engine(url, pool_pre_ping=True, future=True)
    with engine.connect() as connection:
        after = connection.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar()
        applied = connection.execute(text(
            "SELECT version FROM schema_migrations ORDER BY version")).scalars().all()
    engine.dispose()

    print(f"tables in public : {before} -> {after}")
    print("migrations applied:")
    for version in applied:
        print(f"  {version}")
    print("\nNext: create the aashan_app role and grant it, then run scripts/verify_rls.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
