"""Database connection and versioned migration runner."""

from pathlib import Path
import sqlite3
from typing import Optional

from app.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_ROOT = PROJECT_ROOT / "migrations"


def is_sqlite() -> bool:
    return settings.database_url.startswith("sqlite:///")


def sqlite_db_path(database_url: Optional[str] = None) -> str:
    value = database_url or settings.database_url
    if not value.startswith("sqlite:///"):
        raise ValueError("Not a SQLite DATABASE_URL")
    raw = value.replace("sqlite:///", "", 1)
    path = Path(raw)
    return str(path if path.is_absolute() else Path.cwd() / path)


def get_sqlite_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(sqlite_db_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _migration_files(dialect: str) -> list[Path]:
    directory = MIGRATIONS_ROOT / dialect
    return sorted(directory.glob("*.sql"))


def _ensure_sqlite_compatibility(connection: sqlite3.Connection) -> None:
    """Upgrade the pre-Part-1 SQLite tables without deleting demo data."""
    local_user = "00000000-0000-0000-0000-000000000001"

    def columns(table: str) -> set[str]:
        return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}

    def add_column(table: str, definition: str) -> None:
        name = definition.split()[0]
        if name not in columns(table):
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

    for table in ("aggregate_snapshots", "aa_consent_context"):
        if not columns(table):
            continue
        add_column(table, f"user_id TEXT NOT NULL DEFAULT '{local_user}'")
    if columns("aggregate_snapshots"):
        add_column("aggregate_snapshots", "source TEXT NOT NULL DEFAULT 'LEGACY'")
        add_column("aggregate_snapshots", "import_id TEXT")
    if columns("aa_consent_context"):
        add_column("aa_consent_context", "provider TEXT NOT NULL DEFAULT 'SETU'")
        add_column("aa_consent_context", "purpose_json TEXT")
        add_column("aa_consent_context", "connection_id TEXT")

    for table in ("transactions", "transaction_candidates"):
        if not columns(table):
            continue
        add_column(table, "value_date TEXT")
        add_column(table, "mode TEXT")
        add_column(table, "transaction_type TEXT NOT NULL DEFAULT 'DEBIT'")
        add_column(table, "category_candidate TEXT")
        add_column(table, "transaction_status TEXT NOT NULL DEFAULT 'CONFIRMED'")
        add_column(table, "merchant_candidate TEXT")
        add_column(table, "merchant_confidence REAL")
        add_column(table, "duplicate_status TEXT NOT NULL DEFAULT 'NOT_DUPLICATE'")
        add_column(table, "transfer_status TEXT NOT NULL DEFAULT 'NOT_TRANSFER'")
        add_column(table, "budget_status TEXT NOT NULL DEFAULT 'UNDECIDED'")
        add_column(table, "external_id TEXT")
    if columns("merchant_rules"):
        add_column("merchant_rules", "category_name TEXT")

    budget_columns = columns("budgets")
    if budget_columns and "user_id" not in budget_columns:
        connection.execute("ALTER TABLE budgets RENAME TO budgets_legacy")
        connection.execute(
            """CREATE TABLE budgets (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount >= 0),
                period_start TEXT,
                period_end TEXT,
                currency TEXT NOT NULL DEFAULT 'INR',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, category)
            )"""
        )
        connection.execute(
            """INSERT INTO budgets (id, user_id, category, amount)
               SELECT lower(hex(randomblob(16))), ?, category, amount
               FROM budgets_legacy""",
            (local_user,),
        )


def run_sqlite_migrations() -> None:
    path = sqlite_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with get_sqlite_connection() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        # Bring databases that were initialized by the pre-Part-1 code (or
        # partially migrated during an interrupted startup) to the shape
        # expected by the next version before applying new SQL.
        _ensure_sqlite_compatibility(connection)
        for migration in _migration_files("sqlite"):
            version = migration.name
            applied = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
            ).fetchone()
            if applied:
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            # The first migration is intentionally compatible with the
            # pre-Part-1 schema. Upgrade existing global columns before the
            # ownership migration creates indexes that depend on them.
            _ensure_sqlite_compatibility(connection)
            connection.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        _ensure_sqlite_compatibility(connection)


def run_postgres_migrations() -> None:
    """Apply versioned PostgreSQL migrations through SQLAlchemy.

    The PostgreSQL driver is intentionally lazy so SQLite development does not
    require production database credentials or packages at import time.
    """
    try:
        from sqlalchemy import create_engine, text
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("SQLAlchemy is required for PostgreSQL support") from exc
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        for migration in _migration_files("postgres"):
            version = migration.name
            applied = connection.execute(
                text("SELECT 1 FROM schema_migrations WHERE version = :version"),
                {"version": version},
            ).fetchone()
            if applied:
                continue
            for statement in migration.read_text(encoding="utf-8").split(";"):
                statement = statement.strip()
                if statement:
                    connection.exec_driver_sql(statement)
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": version},
            )
    engine.dispose()


def run_migrations() -> None:
    if is_sqlite():
        run_sqlite_migrations()
    else:
        run_postgres_migrations()
