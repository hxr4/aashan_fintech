import uuid

from fastapi.testclient import TestClient

from app.auth import LOCAL_USER_ID
from app.config import settings
from app.database.db import (
    get_budgets,
    get_aa_consent_context,
    init_db,
    save_aa_consent_context,
    save_budgets,
)
from app.database.connection import get_sqlite_connection
from app.main import app
from app.services.pipeline import process_raw_rows


def test_sqlite_migrations_create_identity_foundation_tables():
    init_db()
    with get_sqlite_connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert {
        "schema_migrations",
        "profiles",
        "financial_accounts",
        "account_connections",
        "consents",
        "imports",
        "processing_jobs",
        "transaction_candidates",
        "transactions",
        "transaction_reviews",
        "categories",
        "merchant_rules",
        "budgets",
        "budget_categories",
        "aggregate_snapshots",
        "audit_events",
        "privacy_events",
    }.issubset(tables)


def test_budgets_and_aggregates_are_scoped_by_user():
    init_db()
    user_a = "user-" + uuid.uuid4().hex
    user_b = "user-" + uuid.uuid4().hex
    save_budgets({"Food": 1000}, user_a)
    save_budgets({"Travel": 2000}, user_b)
    assert get_budgets(user_a) == {"Food": 1000}
    assert get_budgets(user_b) == {"Travel": 2000}

    process_raw_rows(
        [{"date": "2026-08-01", "description": "FOOD", "amount": 10, "type": "DEBIT"}],
        user_id=user_a,
        source="TEST",
    )
    process_raw_rows(
        [{"date": "2026-08-01", "description": "TRAVEL", "amount": 20, "type": "DEBIT"}],
        user_id=user_b,
        source="TEST",
    )
    from app.database.db import latest_aggregate

    assert latest_aggregate(user_a)["total_spending"] == 10
    assert latest_aggregate(user_b)["total_spending"] == 20


def test_consent_context_cannot_be_reassigned_between_users():
    init_db()
    consent_id = "consent-" + uuid.uuid4().hex
    save_aa_consent_context(consent_id, "2026-01-01", "2026-02-01", False, "user-a")
    assert get_aa_consent_context(consent_id)["user_id"] == "user-a"
    try:
        save_aa_consent_context(consent_id, "2026-01-01", "2026-02-01", False, "user-b")
    except PermissionError:
        pass
    else:
        raise AssertionError("A consent must not be reassigned to another user")


def test_auth_required_blocks_owned_api_without_bearer(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    try:
        with TestClient(app) as client:
            response = client.get("/api/dashboard/summary")
        assert response.status_code == 401
    finally:
        monkeypatch.setattr(settings, "auth_required", False)


def test_auth_config_never_returns_service_role_key(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "server-only-secret")
    with TestClient(app) as client:
        response = client.get("/api/auth/config")
    assert response.status_code == 200
    assert "server-only-secret" not in response.text
    assert "supabase_service_role_key" not in response.json()
