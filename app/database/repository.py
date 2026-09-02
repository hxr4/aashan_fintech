"""User-scoped repository boundary for SQLite development and PostgreSQL beta."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol

from app.config import settings
from app.database.connection import get_sqlite_connection
from app.models.ingestion import NormalizedTransactionInput


LOCAL_USER_ID = "00000000-0000-0000-0000-000000000001"


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository(Protocol):
    def initialize(self) -> None: ...
    def save_aggregate(self, payload: Dict[str, Any], user_id: str, source: str, import_id: Optional[str]) -> None: ...
    def latest_aggregate(self, user_id: str) -> Dict[str, Any]: ...
    def save_budgets(self, budgets: Dict[str, float], user_id: str) -> None: ...
    def get_budgets(self, user_id: str) -> Dict[str, float]: ...
    def save_aa_consent_context(self, consent_id: str, data_range_from: str, data_range_to: str, auto_fetch: bool, user_id: str, purpose: Optional[Dict[str, Any]] = None) -> None: ...
    def get_aa_consent_context(self, consent_id: str) -> Optional[Dict[str, Any]]: ...
    def update_aa_consent_status(self, consent_id: str, status: str, user_id: Optional[str] = None) -> None: ...
    def mark_aa_webhook_event(self, event_key: str, event_type: str, consent_id: Optional[str], session_id: Optional[str]) -> bool: ...
    def aa_webhook_event_processed(self, event_key: str) -> bool: ...
    def aa_session_processed(self, session_id: str) -> bool: ...
    def mark_aa_session_processed(self, session_id: str) -> None: ...
    def privacy_database_status(self, user_id: str) -> Dict[str, Any]: ...
    def create_import(self, user_id: str, source: str, filename: Optional[str] = None, account_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]: ...
    def complete_import(self, import_id: str, user_id: str, status: str, row_count: int = 0, error_category: Optional[str] = None, error_message: Optional[str] = None) -> None: ...
    def create_processing_job(self, user_id: str, import_id: str, job_type: str) -> str: ...
    def update_processing_checkpoint(self, job_id: str, user_id: str, checkpoint: str, status: Optional[str] = None, progress: Optional[Dict[str, Any]] = None) -> None: ...
    def complete_processing_job(self, job_id: str, user_id: str, status: str = "COMPLETED", error_category: Optional[str] = None, error_message: Optional[str] = None) -> None: ...
    def create_candidate(self, user_id: str, import_id: str, item: NormalizedTransactionInput, category: Optional[str], classification_method: Optional[str], classification_confidence: Optional[float], classification_status: str = "AUTO_CLASSIFIED", review_status: str = "CONFIRMED", transaction_status: str = "CONFIRMED", duplicate_status: str = "NOT_DUPLICATE", budget_status: str = "INCLUDED", transfer_status: str = "NOT_TRANSFER") -> str: ...
    def get_candidate(self, user_id: str, candidate_id: str) -> Optional[Dict[str, Any]]: ...
    def list_candidates(self, user_id: str, review_status: Optional[str] = None) -> list[Dict[str, Any]]: ...
    def update_candidate(self, user_id: str, candidate_id: str, review_status: str, transaction_status: str, classification_status: Optional[str] = None) -> bool: ...
    def create_transaction(self, user_id: str, import_id: str, candidate_id: str, item: NormalizedTransactionInput, category: Optional[str], classification_method: Optional[str], classification_confidence: Optional[float], classification_status: str = "AUTO_CLASSIFIED", transaction_status: str = "CONFIRMED", budget_status: str = "INCLUDED", transfer_status: str = "NOT_TRANSFER", duplicate_status: str = "NOT_DUPLICATE") -> Dict[str, Any]: ...
    def get_transaction(self, user_id: str, transaction_id: str) -> Optional[Dict[str, Any]]: ...
    def list_transactions(self, user_id: str, transaction_status: Optional[str] = "CONFIRMED") -> list[Dict[str, Any]]: ...
    def update_transaction(self, user_id: str, transaction_id: str, updates: Dict[str, Any]) -> bool: ...
    def create_review(self, user_id: str, candidate_id: Optional[str], transaction_id: Optional[str], action: str, changes: Dict[str, Any]) -> str: ...
    def create_merchant_rule(self, user_id: str, merchant_pattern: str, category: Optional[str]) -> str: ...
    def list_merchant_rules(self, user_id: str) -> list[Dict[str, Any]]: ...
    def list_imports(self, user_id: str) -> list[Dict[str, Any]]: ...
    def get_import(self, user_id: str, import_id: str) -> Optional[Dict[str, Any]]: ...


class SQLiteRepository:
    def initialize(self) -> None:
        from app.database.connection import run_sqlite_migrations
        run_sqlite_migrations()

    def save_aggregate(self, payload: Dict[str, Any], user_id: str, source: str = "PIPELINE", import_id: Optional[str] = None) -> None:
        self.initialize()
        with get_sqlite_connection() as connection:
            connection.execute(
                "INSERT INTO aggregate_snapshots (payload, user_id, source, import_id) VALUES (?, ?, ?, ?)",
                (json.dumps(payload, default=str), user_id, source, import_id),
            )

    def latest_aggregate(self, user_id: str) -> Dict[str, Any]:
        self.initialize()
        with get_sqlite_connection() as connection:
            row = connection.execute(
                "SELECT payload FROM aggregate_snapshots WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return json.loads(row["payload"]) if row else {}

    def save_budgets(self, budgets: Dict[str, float], user_id: str) -> None:
        self.initialize()
        with get_sqlite_connection() as connection:
            connection.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
            connection.executemany(
                """INSERT INTO budgets (id, user_id, category, amount, active, updated_at)
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
                [(_new_id(), user_id, category, float(amount)) for category, amount in budgets.items()],
            )

    def get_budgets(self, user_id: str) -> Dict[str, float]:
        self.initialize()
        with get_sqlite_connection() as connection:
            rows = connection.execute(
                "SELECT category, amount FROM budgets WHERE user_id = ? AND active = 1 ORDER BY category",
                (user_id,),
            ).fetchall()
        return {row["category"]: row["amount"] for row in rows}

    def save_aa_consent_context(self, consent_id: str, data_range_from: str, data_range_to: str, auto_fetch: bool, user_id: str, purpose: Optional[Dict[str, Any]] = None) -> None:
        self.initialize()
        with get_sqlite_connection() as connection:
            existing = connection.execute(
                "SELECT user_id FROM aa_consent_context WHERE consent_id = ?", (consent_id,)
            ).fetchone()
            if existing and existing["user_id"] != user_id:
                raise PermissionError("Consent belongs to another user")
            connection.execute(
                """INSERT INTO aa_consent_context
                   (consent_id, data_range_from, data_range_to, auto_fetch, status, user_id, provider, purpose_json)
                   VALUES (?, ?, ?, ?, 'PENDING', ?, 'SETU', ?)
                   ON CONFLICT(consent_id) DO UPDATE SET
                     data_range_from=excluded.data_range_from,
                     data_range_to=excluded.data_range_to,
                     auto_fetch=excluded.auto_fetch,
                     status='PENDING',
                     purpose_json=excluded.purpose_json""",
                (consent_id, data_range_from, data_range_to, int(auto_fetch), user_id, json.dumps(purpose or {})),
            )
            connection.execute(
                """INSERT INTO consents
                   (id, user_id, provider, provider_consent_id, status, data_range_from, data_range_to, purpose)
                   VALUES (?, ?, 'SETU', ?, 'PENDING', ?, ?, ?)
                   ON CONFLICT(user_id, provider, provider_consent_id) DO UPDATE SET
                     status='PENDING', data_range_from=excluded.data_range_from,
                     data_range_to=excluded.data_range_to, purpose=excluded.purpose,
                     updated_at=CURRENT_TIMESTAMP""",
                (_new_id(), user_id, consent_id, data_range_from, data_range_to, json.dumps(purpose or {})),
            )

    def get_aa_consent_context(self, consent_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with get_sqlite_connection() as connection:
            row = connection.execute(
                "SELECT * FROM aa_consent_context WHERE consent_id = ?", (consent_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_aa_consent_status(self, consent_id: str, status: str, user_id: Optional[str] = None) -> None:
        self.initialize()
        with get_sqlite_connection() as connection:
            if user_id:
                connection.execute(
                    "UPDATE aa_consent_context SET status = ? WHERE consent_id = ? AND user_id = ?",
                    (status, consent_id, user_id),
                )
            else:
                connection.execute(
                    "UPDATE aa_consent_context SET status = ? WHERE consent_id = ?",
                    (status, consent_id),
                )
            if user_id:
                connection.execute(
                    "UPDATE consents SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE provider = 'SETU' AND provider_consent_id = ? AND user_id = ?",
                    (status, consent_id, user_id),
                )
            else:
                connection.execute(
                    "UPDATE consents SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE provider = 'SETU' AND provider_consent_id = ?",
                    (status, consent_id),
                )

    def mark_aa_webhook_event(self, event_key: str, event_type: str, consent_id: Optional[str], session_id: Optional[str]) -> bool:
        self.initialize()
        with get_sqlite_connection() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO aa_webhook_events
                   (event_key, event_type, consent_id, session_id) VALUES (?, ?, ?, ?)""",
                (event_key, event_type, consent_id, session_id),
            )
        return cursor.rowcount == 1

    def aa_webhook_event_processed(self, event_key: str) -> bool:
        self.initialize()
        with get_sqlite_connection() as connection:
            row = connection.execute("SELECT 1 FROM aa_webhook_events WHERE event_key = ?", (event_key,)).fetchone()
        return row is not None

    def aa_session_processed(self, session_id: str) -> bool:
        self.initialize()
        with get_sqlite_connection() as connection:
            row = connection.execute("SELECT 1 FROM aa_processed_sessions WHERE session_id = ?", (session_id,)).fetchone()
        return row is not None

    def mark_aa_session_processed(self, session_id: str) -> None:
        self.initialize()
        with get_sqlite_connection() as connection:
            connection.execute("INSERT OR IGNORE INTO aa_processed_sessions (session_id) VALUES (?)", (session_id,))

    def privacy_database_status(self, user_id: str) -> Dict[str, Any]:
        self.initialize()
        with get_sqlite_connection() as connection:
            tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            aggregate_count = connection.execute(
                "SELECT COUNT(*) AS count FROM aggregate_snapshots WHERE user_id = ?", (user_id,)
            ).fetchone()["count"]
        # `transactions` is the future canonical normalized entity, not a raw
        # source table. It is currently empty; raw source persistence is
        # represented only by these explicitly raw tables.
        raw_table_names = {"raw_transactions", "sms_messages", "aa_payloads"}
        return {
            "raw_transaction_count_in_memory": 0,
            "raw_transactions_persisted": bool(tables & raw_table_names),
            "aggregate_data_persisted": aggregate_count > 0,
            # Keep the privacy API focused on persisted raw-source tables;
            # the empty canonical transaction table is a future foundation
            # entity and must not be reported as raw transaction retention.
            "persisted_tables": sorted(tables - {"transactions", "transaction_candidates"}),
            "user_id": user_id if user_id != LOCAL_USER_ID else None,
        }

    def create_import(self, user_id: str, source: str, filename: Optional[str] = None, account_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        self.initialize()
        with get_sqlite_connection() as connection:
            if idempotency_key:
                existing = connection.execute(
                    "SELECT * FROM imports WHERE user_id = ? AND source = ? AND idempotency_key = ?",
                    (user_id, source, idempotency_key),
                ).fetchone()
                if existing:
                    return {**dict(existing), "existing": True}
            import_id = _new_id()
            connection.execute(
                """INSERT INTO imports (id, user_id, source, account_id, status, filename, idempotency_key, started_at)
                   VALUES (?, ?, ?, ?, 'PROCESSING', ?, ?, CURRENT_TIMESTAMP)""",
                (import_id, user_id, source, account_id, filename, idempotency_key),
            )
        return {"id": import_id, "existing": False}

    def complete_import(self, import_id: str, user_id: str, status: str, row_count: int = 0, error_category: Optional[str] = None, error_message: Optional[str] = None) -> None:
        self.initialize()
        with get_sqlite_connection() as connection:
            connection.execute(
                """UPDATE imports SET status = ?, row_count = ?, error_category = ?, error_message = ?,
                   completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND user_id = ?""",
                (status, row_count, error_category, error_message, import_id, user_id),
            )

    def create_processing_job(self, user_id: str, import_id: str, job_type: str) -> str:
        self.initialize()
        job_id = _new_id()
        with get_sqlite_connection() as connection:
            connection.execute(
                "INSERT INTO processing_jobs (id, user_id, import_id, job_type, status) VALUES (?, ?, ?, ?, 'QUEUED')",
                (job_id, user_id, import_id, job_type),
            )
        return job_id

    def update_processing_checkpoint(self, job_id: str, user_id: str, checkpoint: str, status: Optional[str] = None, progress: Optional[Dict[str, Any]] = None) -> None:
        self.initialize()
        with get_sqlite_connection() as connection:
            row = connection.execute("SELECT progress FROM processing_jobs WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()
            if not row:
                raise PermissionError("Processing job not found")
            current = json.loads(row["progress"] or "{}")
            current[checkpoint] = {"at": _now(), **(progress or {})}
            connection.execute(
                "UPDATE processing_jobs SET status = COALESCE(?, 'RUNNING'), progress = ?, started_at = COALESCE(started_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (status, json.dumps(current), job_id, user_id),
            )

    def complete_processing_job(self, job_id: str, user_id: str, status: str = "COMPLETED", error_category: Optional[str] = None, error_message: Optional[str] = None) -> None:
        self.initialize()
        with get_sqlite_connection() as connection:
            connection.execute(
                "UPDATE processing_jobs SET status = ?, error_category = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (status, error_category, error_message, job_id, user_id),
            )

    @staticmethod
    def _item_values(item: NormalizedTransactionInput) -> tuple[Any, ...]:
        return (
            item.transaction_at.isoformat(),
            item.value_date.isoformat() if item.value_date else None,
            item.amount,
            item.currency,
            item.direction,
            item.transaction_type,
            item.description,
            item.mode,
            item.merchant_candidate,
            item.merchant_confidence,
            item.source_type,
            item.source_record_id,
            item.external_id,
            item.account_id,
        )

    def create_candidate(self, user_id: str, import_id: str, item: NormalizedTransactionInput, category: Optional[str], classification_method: Optional[str], classification_confidence: Optional[float], classification_status: str = "AUTO_CLASSIFIED", review_status: str = "CONFIRMED", transaction_status: str = "CONFIRMED", duplicate_status: str = "NOT_DUPLICATE", budget_status: str = "INCLUDED", transfer_status: str = "NOT_TRANSFER") -> str:
        self.initialize()
        candidate_id = _new_id()
        with get_sqlite_connection() as connection:
            connection.execute(
                """INSERT INTO transaction_candidates
                   (id, user_id, account_id, import_id, source, source_record_id, external_id,
                    transaction_at, value_date, amount, currency, direction, transaction_type,
                    description, mode, merchant_candidate, merchant_confidence, category_candidate,
                    classification_status, review_status, transaction_status, duplicate_status,
                    budget_status, transfer_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (candidate_id, user_id, item.account_id, import_id, item.source_type, item.source_record_id, item.external_id,
                 *self._item_values(item)[:10], category, classification_status, review_status, transaction_status,
                 duplicate_status, budget_status, transfer_status),
            )
        return candidate_id

    def get_candidate(self, user_id: str, candidate_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with get_sqlite_connection() as connection:
            row = connection.execute("SELECT * FROM transaction_candidates WHERE id = ? AND user_id = ?", (candidate_id, user_id)).fetchone()
        return dict(row) if row else None

    def list_candidates(self, user_id: str, review_status: Optional[str] = None) -> list[Dict[str, Any]]:
        self.initialize()
        query = "SELECT * FROM transaction_candidates WHERE user_id = ?"
        params: list[Any] = [user_id]
        if review_status:
            query += " AND review_status = ?"
            params.append(review_status)
        query += " ORDER BY created_at DESC"
        with get_sqlite_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_candidate(self, user_id: str, candidate_id: str, review_status: str, transaction_status: str, classification_status: Optional[str] = None) -> bool:
        self.initialize()
        with get_sqlite_connection() as connection:
            cursor = connection.execute(
                "UPDATE transaction_candidates SET review_status = ?, transaction_status = ?, classification_status = COALESCE(?, classification_status), updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (review_status, transaction_status, classification_status, candidate_id, user_id),
            )
        return cursor.rowcount == 1

    def create_transaction(self, user_id: str, import_id: str, candidate_id: str, item: NormalizedTransactionInput, category: Optional[str], classification_method: Optional[str], classification_confidence: Optional[float], classification_status: str = "AUTO_CLASSIFIED", transaction_status: str = "CONFIRMED", budget_status: str = "INCLUDED", transfer_status: str = "NOT_TRANSFER", duplicate_status: str = "NOT_DUPLICATE") -> Dict[str, Any]:
        self.initialize()
        with get_sqlite_connection() as connection:
            if item.external_id:
                existing = connection.execute(
                    "SELECT id FROM transactions WHERE user_id = ? AND source = ? AND external_id = ?",
                    (user_id, item.source_type, item.external_id),
                ).fetchone()
                if existing:
                    return {"created": False, "duplicate": True, "possible_duplicate": False, "id": existing["id"]}
            transaction_id = _new_id()
            connection.execute(
                """INSERT INTO transactions
                   (id, user_id, account_id, import_id, source, source_record_id, external_id,
                   transaction_at, value_date, amount, currency, direction, transaction_type,
                    description, mode, merchant_candidate, merchant_confidence, category_name,
                    classification_method, classification_confidence, classification_status,
                    status, transaction_status, budget_inclusion, budget_status, transfer_status,
                    duplicate_status, is_transfer)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (transaction_id, user_id, item.account_id, import_id, item.source_type, item.source_record_id, item.external_id,
                 item.transaction_at.isoformat(), item.value_date.isoformat() if item.value_date else None,
                 item.amount, item.currency, item.direction, item.transaction_type, item.description,
                 item.mode, item.merchant_candidate, item.merchant_confidence, category, classification_method,
                 classification_confidence, classification_status, transaction_status, transaction_status,
                 budget_status, budget_status, transfer_status, duplicate_status, transfer_status == "CONFIRMED"),
            )
        return {"created": True, "duplicate": False, "possible_duplicate": False, "id": transaction_id}

    def get_transaction(self, user_id: str, transaction_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with get_sqlite_connection() as connection:
            row = connection.execute("SELECT * FROM transactions WHERE id = ? AND user_id = ?", (transaction_id, user_id)).fetchone()
        return dict(row) if row else None

    def list_transactions(self, user_id: str, transaction_status: Optional[str] = "CONFIRMED") -> list[Dict[str, Any]]:
        self.initialize()
        query = "SELECT * FROM transactions WHERE user_id = ?"
        params: list[Any] = [user_id]
        if transaction_status:
            query += " AND transaction_status = ?"
            params.append(transaction_status)
        query += " ORDER BY transaction_at DESC, created_at DESC"
        with get_sqlite_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_transaction(self, user_id: str, transaction_id: str, updates: Dict[str, Any]) -> bool:
        self.initialize()
        allowed = {"category_name", "merchant_candidate", "classification_status", "budget_status", "budget_inclusion", "transaction_type", "transaction_status", "status", "transfer_status", "duplicate_status", "is_transfer"}
        changes = {key: value for key, value in updates.items() if key in allowed}
        if not changes:
            return False
        assignments = ", ".join(f"{key} = ?" for key in changes)
        values = list(changes.values()) + [transaction_id, user_id]
        with get_sqlite_connection() as connection:
            cursor = connection.execute(f"UPDATE transactions SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?", values)
        return cursor.rowcount == 1

    def create_review(self, user_id: str, candidate_id: Optional[str], transaction_id: Optional[str], action: str, changes: Dict[str, Any]) -> str:
        self.initialize()
        review_id = _new_id()
        with get_sqlite_connection() as connection:
            connection.execute(
                "INSERT INTO transaction_reviews (id, user_id, transaction_id, candidate_id, action, changes) VALUES (?, ?, ?, ?, ?, ?)",
                (review_id, user_id, transaction_id, candidate_id, action, json.dumps(changes)),
            )
        return review_id

    def create_merchant_rule(self, user_id: str, merchant_pattern: str, category: Optional[str]) -> str:
        self.initialize()
        rule_id = _new_id()
        with get_sqlite_connection() as connection:
            connection.execute(
                "INSERT INTO merchant_rules (id, user_id, merchant_pattern, category_name) VALUES (?, ?, ?, ?)",
                (rule_id, user_id, merchant_pattern, category),
            )
        return rule_id

    def list_merchant_rules(self, user_id: str) -> list[Dict[str, Any]]:
        self.initialize()
        with get_sqlite_connection() as connection:
            rows = connection.execute("SELECT * FROM merchant_rules WHERE user_id = ? AND active = 1 ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def list_imports(self, user_id: str) -> list[Dict[str, Any]]:
        self.initialize()
        with get_sqlite_connection() as connection:
            rows = connection.execute("SELECT * FROM imports WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_import(self, user_id: str, import_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with get_sqlite_connection() as connection:
            row = connection.execute("SELECT * FROM imports WHERE id = ? AND user_id = ?", (import_id, user_id)).fetchone()
        return dict(row) if row else None


class PostgresRepository:
    def __init__(self) -> None:
        try:
            from sqlalchemy import create_engine
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("SQLAlchemy is required for PostgreSQL support") from exc
        self._engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

    def initialize(self) -> None:
        from app.database.connection import run_postgres_migrations
        run_postgres_migrations()

    def _text(self, query: str):
        from sqlalchemy import text
        return text(query)

    def _set_user_context(self, connection, user_id: str) -> None:
        """Expose the validated request owner to Supabase RLS for this transaction.

        The FastAPI dependency remains the primary authorization check. This
        transaction-local claim gives RLS an owner context when the application
        connects through a role that does not bypass RLS.
        """
        claims = json.dumps({"sub": user_id, "role": "authenticated"})
        connection.execute(
            self._text(
                "SELECT set_config('request.jwt.claims', :claims, true), "
                "set_config('request.jwt.claim.sub', :user_id, true)"
            ),
            {"claims": claims, "user_id": user_id},
        )

    def save_aggregate(self, payload: Dict[str, Any], user_id: str, source: str = "PIPELINE", import_id: Optional[str] = None) -> None:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            connection.execute(self._text("INSERT INTO aggregate_snapshots (user_id, source, import_id, payload) VALUES (:user_id, :source, :import_id, CAST(:payload AS jsonb))"), {"user_id": user_id, "source": source, "import_id": import_id, "payload": json.dumps(payload, default=str)})

    def latest_aggregate(self, user_id: str) -> Dict[str, Any]:
        self.initialize()
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            row = connection.execute(self._text("SELECT payload FROM aggregate_snapshots WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 1"), {"user_id": user_id}).mappings().first()
        return dict(row["payload"]) if row else {}

    def save_budgets(self, budgets: Dict[str, float], user_id: str) -> None:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            connection.execute(self._text("DELETE FROM budgets WHERE user_id = :user_id"), {"user_id": user_id})
            for category, amount in budgets.items():
                connection.execute(self._text("INSERT INTO budgets (user_id, category, amount) VALUES (:user_id, :category, :amount)"), {"user_id": user_id, "category": category, "amount": float(amount)})

    def get_budgets(self, user_id: str) -> Dict[str, float]:
        self.initialize()
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            rows = connection.execute(self._text("SELECT category, amount FROM budgets WHERE user_id = :user_id AND active = TRUE ORDER BY category"), {"user_id": user_id}).mappings().all()
        return {row["category"]: float(row["amount"]) for row in rows}

    def save_aa_consent_context(self, consent_id: str, data_range_from: str, data_range_to: str, auto_fetch: bool, user_id: str, purpose: Optional[Dict[str, Any]] = None) -> None:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            existing = connection.execute(self._text("SELECT user_id FROM consents WHERE provider = 'SETU' AND provider_consent_id = :consent_id"), {"consent_id": consent_id}).mappings().first()
            if existing and str(existing["user_id"]) != user_id:
                raise PermissionError("Consent belongs to another user")
            connection.execute(self._text("INSERT INTO consents (user_id, provider, provider_consent_id, status, data_range_from, data_range_to, purpose) VALUES (:user_id, 'SETU', :consent_id, 'PENDING', CAST(:data_from AS timestamptz), CAST(:data_to AS timestamptz), CAST(:purpose AS jsonb)) ON CONFLICT (user_id, provider, provider_consent_id) DO UPDATE SET status = 'PENDING', data_range_from = EXCLUDED.data_range_from, data_range_to = EXCLUDED.data_range_to, purpose = EXCLUDED.purpose, updated_at = now()"), {"user_id": user_id, "consent_id": consent_id, "data_from": data_range_from, "data_to": data_range_to, "purpose": json.dumps(purpose or {})})

    def get_aa_consent_context(self, consent_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with self._engine.connect() as connection:
            row = connection.execute(self._text("SELECT provider_consent_id AS consent_id, user_id, data_range_from, data_range_to, status, purpose AS purpose_json FROM consents WHERE provider = 'SETU' AND provider_consent_id = :consent_id"), {"consent_id": consent_id}).mappings().first()
        if not row:
            return None
        result = dict(row)
        result["auto_fetch"] = bool(settings.setu_auto_fetch)
        return result

    def update_aa_consent_status(self, consent_id: str, status: str, user_id: Optional[str] = None) -> None:
        self.initialize()
        clause = "provider_consent_id = :consent_id"
        params: Dict[str, Any] = {"consent_id": consent_id, "status": status}
        if user_id:
            clause += " AND user_id = :user_id"
            params["user_id"] = user_id
        with self._engine.begin() as connection:
            if user_id:
                self._set_user_context(connection, user_id)
            connection.execute(self._text(f"UPDATE consents SET status = :status, updated_at = now() WHERE provider = 'SETU' AND {clause}"), params)

    def mark_aa_webhook_event(self, event_key: str, event_type: str, consent_id: Optional[str], session_id: Optional[str]) -> bool:
        self.initialize()
        with self._engine.begin() as connection:
            result = connection.execute(self._text("INSERT INTO audit_events (user_id, event_type, entity_type, entity_id, metadata) VALUES (NULL, :event_type, 'SETU_WEBHOOK', :event_key, CAST(:metadata AS jsonb)) ON CONFLICT DO NOTHING"), {"event_type": event_type, "event_key": event_key, "metadata": json.dumps({"consent_id": consent_id, "session_id": session_id})})
        return result.rowcount == 1

    def aa_webhook_event_processed(self, event_key: str) -> bool:
        self.initialize()
        with self._engine.connect() as connection:
            row = connection.execute(self._text("SELECT 1 FROM audit_events WHERE entity_type = 'SETU_WEBHOOK' AND entity_id = :event_key"), {"event_key": event_key}).first()
        return row is not None

    def aa_session_processed(self, session_id: str) -> bool:
        self.initialize()
        with self._engine.connect() as connection:
            row = connection.execute(self._text("SELECT 1 FROM audit_events WHERE entity_type = 'SETU_SESSION' AND entity_id = :session_id"), {"session_id": session_id}).first()
        return row is not None

    def mark_aa_session_processed(self, session_id: str) -> None:
        self.initialize()
        with self._engine.begin() as connection:
            connection.execute(self._text("INSERT INTO audit_events (user_id, event_type, entity_type, entity_id, metadata) VALUES (NULL, 'SETU_SESSION_PROCESSED', 'SETU_SESSION', :session_id, '{}'::jsonb) ON CONFLICT DO NOTHING"), {"session_id": session_id})

    def privacy_database_status(self, user_id: str) -> Dict[str, Any]:
        self.initialize()
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            aggregate_count = connection.execute(self._text("SELECT COUNT(*) FROM aggregate_snapshots WHERE user_id = :user_id"), {"user_id": user_id}).scalar_one()
        return {"raw_transaction_count_in_memory": 0, "raw_transactions_persisted": False, "aggregate_data_persisted": aggregate_count > 0, "persisted_tables": [], "user_id": user_id}

    def create_import(self, user_id: str, source: str, filename: Optional[str] = None, account_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            if idempotency_key:
                existing = connection.execute(self._text("SELECT id, status, row_count FROM imports WHERE user_id = :user_id AND source = :source AND idempotency_key = :key"), {"user_id": user_id, "source": source, "key": idempotency_key}).mappings().first()
                if existing:
                    return {**dict(existing), "existing": True}
            row = connection.execute(self._text("INSERT INTO imports (user_id, source, account_id, status, filename, idempotency_key, started_at) VALUES (:user_id, :source, :account_id, 'PROCESSING', :filename, :key, now()) RETURNING id"), {"user_id": user_id, "source": source, "account_id": account_id, "filename": filename, "key": idempotency_key}).mappings().first()
        return {"id": str(row["id"]), "existing": False}

    def complete_import(self, import_id: str, user_id: str, status: str, row_count: int = 0, error_category: Optional[str] = None, error_message: Optional[str] = None) -> None:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            connection.execute(self._text("UPDATE imports SET status = :status, row_count = :row_count, error_category = :error_category, error_message = :error_message, completed_at = now(), updated_at = now() WHERE id = :id AND user_id = :user_id"), {"status": status, "row_count": row_count, "error_category": error_category, "error_message": error_message, "id": import_id, "user_id": user_id})

    def create_processing_job(self, user_id: str, import_id: str, job_type: str) -> str:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            row = connection.execute(self._text("INSERT INTO processing_jobs (user_id, import_id, job_type, status) VALUES (:user_id, :import_id, :job_type, 'QUEUED') RETURNING id"), {"user_id": user_id, "import_id": import_id, "job_type": job_type}).mappings().first()
        return str(row["id"])

    def update_processing_checkpoint(self, job_id: str, user_id: str, checkpoint: str, status: Optional[str] = None, progress: Optional[Dict[str, Any]] = None) -> None:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            current = connection.execute(self._text("SELECT progress FROM processing_jobs WHERE id = :id AND user_id = :user_id"), {"id": job_id, "user_id": user_id}).mappings().first()
            if not current:
                raise PermissionError("Processing job not found")
            state = dict(current["progress"] or {})
            state[checkpoint] = {"at": _now(), **(progress or {})}
            connection.execute(self._text("UPDATE processing_jobs SET status = COALESCE(:status, 'RUNNING'), progress = CAST(:progress AS jsonb), started_at = COALESCE(started_at, now()), updated_at = now() WHERE id = :id AND user_id = :user_id"), {"status": status, "progress": json.dumps(state), "id": job_id, "user_id": user_id})

    def complete_processing_job(self, job_id: str, user_id: str, status: str = "COMPLETED", error_category: Optional[str] = None, error_message: Optional[str] = None) -> None:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            connection.execute(self._text("UPDATE processing_jobs SET status = :status, error_category = :error_category, error_message = :error_message, completed_at = now(), updated_at = now() WHERE id = :id AND user_id = :user_id"), {"status": status, "error_category": error_category, "error_message": error_message, "id": job_id, "user_id": user_id})

    @staticmethod
    def _canonical_params(item: NormalizedTransactionInput) -> Dict[str, Any]:
        return {
            "account_id": item.account_id,
            "source": item.source_type,
            "source_record_id": item.source_record_id,
            "external_id": item.external_id,
            "transaction_at": item.transaction_at,
            "value_date": item.value_date,
            "amount": item.amount,
            "currency": item.currency,
            "direction": item.direction,
            "transaction_type": item.transaction_type,
            "description": item.description,
            "mode": item.mode,
            "merchant_candidate": item.merchant_candidate,
            "merchant_confidence": item.merchant_confidence,
        }

    def create_candidate(self, user_id: str, import_id: str, item: NormalizedTransactionInput, category: Optional[str], classification_method: Optional[str], classification_confidence: Optional[float], classification_status: str = "AUTO_CLASSIFIED", review_status: str = "CONFIRMED", transaction_status: str = "CONFIRMED", duplicate_status: str = "NOT_DUPLICATE", budget_status: str = "INCLUDED", transfer_status: str = "NOT_TRANSFER") -> str:
        self.initialize()
        params = {**self._canonical_params(item), "user_id": user_id, "import_id": import_id, "category": category, "classification_method": classification_method, "classification_confidence": classification_confidence, "classification_status": classification_status, "review_status": review_status, "transaction_status": transaction_status, "duplicate_status": duplicate_status, "budget_status": budget_status, "transfer_status": transfer_status}
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            row = connection.execute(self._text("""INSERT INTO transaction_candidates
                (user_id, account_id, import_id, source, source_record_id, external_id, transaction_at, value_date,
                 amount, currency, direction, transaction_type, description, mode, merchant_candidate, merchant_confidence,
                 category_candidate, classification_status, review_status, transaction_status, duplicate_status, budget_status, transfer_status)
                VALUES (:user_id, :account_id, :import_id, :source, :source_record_id, :external_id, :transaction_at, :value_date,
                 :amount, :currency, :direction, :transaction_type, :description, :mode, :merchant_candidate, :merchant_confidence,
                 :category, :classification_status, :review_status, :transaction_status, :duplicate_status, :budget_status, :transfer_status)
                RETURNING id"""), params).mappings().first()
        return str(row["id"])

    def get_candidate(self, user_id: str, candidate_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            row = connection.execute(self._text("SELECT * FROM transaction_candidates WHERE id = :id AND user_id = :user_id"), {"id": candidate_id, "user_id": user_id}).mappings().first()
        return dict(row) if row else None

    def list_candidates(self, user_id: str, review_status: Optional[str] = None) -> list[Dict[str, Any]]:
        self.initialize()
        query = "SELECT * FROM transaction_candidates WHERE user_id = :user_id"
        params: Dict[str, Any] = {"user_id": user_id}
        if review_status:
            query += " AND review_status = :review_status"
            params["review_status"] = review_status
        query += " ORDER BY created_at DESC"
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            rows = connection.execute(self._text(query), params).mappings().all()
        return [dict(row) for row in rows]

    def update_candidate(self, user_id: str, candidate_id: str, review_status: str, transaction_status: str, classification_status: Optional[str] = None) -> bool:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            result = connection.execute(self._text("UPDATE transaction_candidates SET review_status = :review_status, transaction_status = :transaction_status, classification_status = COALESCE(:classification_status, classification_status), updated_at = now() WHERE id = :id AND user_id = :user_id"), {"review_status": review_status, "transaction_status": transaction_status, "classification_status": classification_status, "id": candidate_id, "user_id": user_id})
        return result.rowcount == 1

    def create_transaction(self, user_id: str, import_id: str, candidate_id: str, item: NormalizedTransactionInput, category: Optional[str], classification_method: Optional[str], classification_confidence: Optional[float], classification_status: str = "AUTO_CLASSIFIED", transaction_status: str = "CONFIRMED", budget_status: str = "INCLUDED", transfer_status: str = "NOT_TRANSFER", duplicate_status: str = "NOT_DUPLICATE") -> Dict[str, Any]:
        self.initialize()
        params = {**self._canonical_params(item), "user_id": user_id, "import_id": import_id, "candidate_id": candidate_id, "category": category, "classification_method": classification_method, "classification_confidence": classification_confidence, "classification_status": classification_status, "transaction_status": transaction_status, "budget_status": budget_status, "transfer_status": transfer_status, "duplicate_status": duplicate_status}
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            if item.external_id:
                existing = connection.execute(self._text("SELECT id FROM transactions WHERE user_id = :user_id AND source = :source AND external_id = :external_id"), {"user_id": user_id, "source": item.source_type, "external_id": item.external_id}).mappings().first()
                if existing:
                    return {"created": False, "duplicate": True, "possible_duplicate": False, "id": str(existing["id"])}
            row = connection.execute(self._text("""INSERT INTO transactions
                (user_id, account_id, import_id, source, source_record_id, external_id, transaction_at, value_date,
                 amount, currency, direction, transaction_type, description, mode, merchant_candidate, merchant_confidence,
                 category_name, classification_method, classification_confidence, classification_status, status,
                 transaction_status, budget_inclusion, budget_status, transfer_status, duplicate_status, is_transfer)
                VALUES (:user_id, :account_id, :import_id, :source, :source_record_id, :external_id, :transaction_at, :value_date,
                 :amount, :currency, :direction, :transaction_type, :description, :mode, :merchant_candidate, :merchant_confidence,
                 :category, :classification_method, :classification_confidence, :classification_status, :transaction_status,
                 :transaction_status, :budget_status, :budget_status, :transfer_status, :duplicate_status, :is_transfer)
                RETURNING id"""), {**params, "is_transfer": transfer_status == "CONFIRMED"}).mappings().first()
        return {"created": True, "duplicate": False, "possible_duplicate": False, "id": str(row["id"])}

    def get_transaction(self, user_id: str, transaction_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            row = connection.execute(self._text("SELECT * FROM transactions WHERE id = :id AND user_id = :user_id"), {"id": transaction_id, "user_id": user_id}).mappings().first()
        return dict(row) if row else None

    def list_transactions(self, user_id: str, transaction_status: Optional[str] = "CONFIRMED") -> list[Dict[str, Any]]:
        self.initialize()
        query = "SELECT * FROM transactions WHERE user_id = :user_id"
        params: Dict[str, Any] = {"user_id": user_id}
        if transaction_status:
            query += " AND transaction_status = :transaction_status"
            params["transaction_status"] = transaction_status
        query += " ORDER BY transaction_at DESC, created_at DESC"
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            rows = connection.execute(self._text(query), params).mappings().all()
        return [dict(row) for row in rows]

    def update_transaction(self, user_id: str, transaction_id: str, updates: Dict[str, Any]) -> bool:
        self.initialize()
        allowed = {"category_name", "merchant_candidate", "classification_status", "budget_status", "budget_inclusion", "transaction_type", "transaction_status", "status", "transfer_status", "duplicate_status", "is_transfer"}
        changes = {key: value for key, value in updates.items() if key in allowed}
        if not changes:
            return False
        assignments = ", ".join(f"{key} = :{key}" for key in changes)
        params = {**changes, "id": transaction_id, "user_id": user_id}
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            result = connection.execute(self._text(f"UPDATE transactions SET {assignments}, updated_at = now() WHERE id = :id AND user_id = :user_id"), params)
        return result.rowcount == 1

    def create_review(self, user_id: str, candidate_id: Optional[str], transaction_id: Optional[str], action: str, changes: Dict[str, Any]) -> str:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            row = connection.execute(self._text("INSERT INTO transaction_reviews (user_id, candidate_id, transaction_id, action, changes) VALUES (:user_id, :candidate_id, :transaction_id, :action, CAST(:changes AS jsonb)) RETURNING id"), {"user_id": user_id, "candidate_id": candidate_id, "transaction_id": transaction_id, "action": action, "changes": json.dumps(changes)}).mappings().first()
        return str(row["id"])

    def create_merchant_rule(self, user_id: str, merchant_pattern: str, category: Optional[str]) -> str:
        self.initialize()
        with self._engine.begin() as connection:
            self._set_user_context(connection, user_id)
            row = connection.execute(self._text("INSERT INTO merchant_rules (user_id, merchant_pattern, category_name) VALUES (:user_id, :pattern, :category) RETURNING id"), {"user_id": user_id, "pattern": merchant_pattern, "category": category}).mappings().first()
        return str(row["id"])

    def list_merchant_rules(self, user_id: str) -> list[Dict[str, Any]]:
        self.initialize()
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            rows = connection.execute(self._text("SELECT * FROM merchant_rules WHERE user_id = :user_id AND active = TRUE ORDER BY created_at DESC"), {"user_id": user_id}).mappings().all()
        return [dict(row) for row in rows]

    def list_imports(self, user_id: str) -> list[Dict[str, Any]]:
        self.initialize()
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            rows = connection.execute(self._text("SELECT * FROM imports WHERE user_id = :user_id ORDER BY created_at DESC"), {"user_id": user_id}).mappings().all()
        return [dict(row) for row in rows]

    def get_import(self, user_id: str, import_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with self._engine.connect() as connection:
            self._set_user_context(connection, user_id)
            row = connection.execute(self._text("SELECT * FROM imports WHERE id = :id AND user_id = :user_id"), {"id": import_id, "user_id": user_id}).mappings().first()
        return dict(row) if row else None


_repositories: Dict[str, Repository] = {}


def get_repository() -> Repository:
    key = settings.database_url
    if key not in _repositories:
        _repositories[key] = SQLiteRepository() if key.startswith("sqlite:///") else PostgresRepository()
    return _repositories[key]
