import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.database import db
from app.database.connection import get_sqlite_connection
from app.main import app
from app.models.ingestion import NormalizedTransactionInput, TransactionReviewRequest
from app.services.ingestion import CSVAdapter, SetuAdapter
from app.services.ingestion.service import ingest_with_adapter
from app.services.pipeline import process_raw_rows
from app.services.review import review_candidate


def _user() -> str:
    return "user-" + uuid.uuid4().hex


def _token(user_id: str) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "aud": "authenticated",
            "iss": "https://identity.example.test/auth/v1",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "part-2-test-secret-0123456789012345",
        algorithm="HS256",
    )


def _item(user_id: str, *, external_id: Optional[str] = None, amount: float = 100) -> tuple[str, NormalizedTransactionInput]:
    import_record = db.create_import(user_id, "MANUAL")
    item = NormalizedTransactionInput(
        transaction_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        value_date=datetime(2026, 8, 15, tzinfo=timezone.utc),
        amount=amount,
        direction="DEBIT",
        transaction_type="DEBIT",
        description="TEST GROCERY",
        mode="UPI",
        source_type="MANUAL",
        source_record_id="record-1",
        external_id=external_id,
    )
    return import_record["id"], item


def test_csv_adapter_creates_owned_import_transactions_and_is_idempotent():
    user_id = _user()
    content = b"date,description,amount,mode,type\n2026-08-15,TEST GROCERY,100,UPI,DEBIT\n"
    first = ingest_with_adapter(CSVAdapter(), content, user_id, idempotency_key="csv-import-1")
    second = ingest_with_adapter(CSVAdapter(), content, user_id, idempotency_key="csv-import-1")

    assert first["status"] == "processed"
    assert first["rows_confirmed"] == 1
    assert second["status"] == "already_processed"
    assert len(db.list_imports(user_id)) == 1
    assert len(db.list_transactions(user_id)) == 1
    assert db.list_transactions(user_id)[0]["user_id"] == user_id


def test_user_a_cannot_read_user_b_imports_or_transactions(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "supabase_url", "https://identity.example.test")
    monkeypatch.setattr(settings, "supabase_jwt_secret", "part-2-test-secret-0123456789012345")
    monkeypatch.setattr(settings, "supabase_jwt_issuer", "https://identity.example.test/auth/v1")
    user_a, user_b = _user(), _user()
    try:
        with TestClient(app) as client:
            imported = client.post(
                "/api/ingest/csv",
                headers={"Authorization": f"Bearer {_token(user_a)}"},
                files={"file": ("owned.csv", "date,description,amount,mode,type\n2026-08-15,FOOD,50,UPI,DEBIT\n", "text/csv")},
            )
            assert imported.status_code == 200
            import_id = imported.json()["import_id"]
            assert client.get("/api/transactions", headers={"Authorization": f"Bearer {_token(user_a)}"}).json()["transactions"]
            assert client.get("/api/transactions", headers={"Authorization": f"Bearer {_token(user_b)}"}).json()["transactions"] == []
            assert client.get(f"/api/imports/{import_id}", headers={"Authorization": f"Bearer {_token(user_b)}"}).status_code == 404
            assert client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {_token(user_b)}"}).json()["total_spending"] == 0
    finally:
        monkeypatch.setattr(settings, "auth_required", False)


def test_pending_candidate_does_not_affect_aggregate_until_review():
    user_id = _user()
    import_id, item = _item(user_id)
    candidate_id = db.create_candidate(
        user_id,
        import_id,
        item,
        "Food",
        "fallback",
        0.0,
        classification_status="AMBIGUOUS",
        review_status="PENDING_REVIEW",
        transaction_status="PENDING_REVIEW",
        budget_status="UNDECIDED",
    )
    assert db.latest_aggregate(user_id) == {}
    result = review_candidate(user_id, candidate_id, TransactionReviewRequest(action="APPROVE"))
    assert result["status"] == "CONFIRMED"
    assert result["aggregate"]["total_spending"] == 100
    assert len(db.list_transactions(user_id)) == 1


def test_strong_external_id_duplicate_is_ignored():
    user_id = _user()
    import_id, item = _item(user_id, external_id="bank-reference-1")
    first_candidate = db.create_candidate(user_id, import_id, item, "Food", "merchant_rule", 0.99)
    first = db.create_transaction(user_id, import_id, first_candidate, item, "Food", "merchant_rule", 0.99)
    import_id_2, item_2 = _item(user_id, external_id="bank-reference-1")
    second_candidate = db.create_candidate(user_id, import_id_2, item_2, "Food", "merchant_rule", 0.99)
    second = db.create_transaction(user_id, import_id_2, second_candidate, item_2, "Food", "merchant_rule", 0.99)
    assert first["created"] is True
    assert second["duplicate"] is True
    assert len(db.list_transactions(user_id)) == 1


def test_csv_adapter_extracts_strong_reference_for_deduplication():
    item = next(CSVAdapter().extract(
        b"date,description,amount,mode,type,reference\n2026-08-15,FOOD,100,UPI,DEBIT,bank-ref-42\n"
    ))
    assert item.external_id == "bank-ref-42"


def test_transfer_is_not_income_or_spending():
    user_id = _user()
    aggregate = process_raw_rows([
        {"date": "2026-08-15", "description": "SALARY", "amount": 500, "type": "CREDIT"},
        {"date": "2026-08-15", "description": "GROCERY", "amount": 100, "type": "DEBIT"},
        {"date": "2026-08-15", "description": "OWN ACCOUNT TRANSFER", "amount": 250, "type": "TRANSFER"},
    ], user_id=user_id)
    assert aggregate["total_credit"] == 500
    assert aggregate["total_debit"] == 100
    assert aggregate["total_spending"] == 100
    assert aggregate["net_cash_flow"] == 400


def test_source_adapters_preserve_transfer_direction():
    csv_item = next(CSVAdapter().extract(
        b"date,description,amount,mode,type\n2026-08-15,OWN ACCOUNT TRANSFER,250,NEFT,TRANSFER\n"
    ))
    assert csv_item.direction == "TRANSFER"
    assert csv_item.transaction_type == "TRANSFER"

    setu_item = next(SetuAdapter().extract({"rows": [{
        "date": "2026-08-15",
        "description": "OWN ACCOUNT TRANSFER",
        "amount": 250,
        "mode": "NEFT",
        "transaction_type": "TRANSFER",
    }]}))
    assert setu_item.direction == "TRANSFER"
    assert setu_item.transaction_type == "TRANSFER"


def test_budget_exclusion_only_changes_budget_eligible_totals():
    user_id = _user()
    aggregate = process_raw_rows([
        {"date": "2026-08-15", "description": "FOOD INCLUDED", "amount": 100, "type": "DEBIT", "budget_status": "INCLUDED"},
        {"date": "2026-08-15", "description": "FOOD EXCLUDED", "amount": 75, "type": "DEBIT", "budget_status": "EXCLUDED"},
    ], {"Food": 150}, user_id=user_id)
    assert aggregate["total_spending"] == 175
    assert aggregate["budget_categories"]["Food"] == 100
    assert aggregate["budget_status"][0]["spent"] == 100


def test_review_correction_is_user_specific_and_auditable():
    user_id = _user()
    import_id, item = _item(user_id)
    candidate_id = db.create_candidate(user_id, import_id, item, "Other", "fallback", 0.0, classification_status="AMBIGUOUS", review_status="PENDING_REVIEW", transaction_status="PENDING_REVIEW")
    result = review_candidate(user_id, candidate_id, TransactionReviewRequest(action="CORRECT_CATEGORY", category="Food", merchant="campus-canteen"))
    transaction = db.get_transaction(user_id, result["transaction_id"])
    assert transaction["category_name"] == "Food"
    assert transaction["classification_status"] == "USER_CORRECTED"
    with get_sqlite_connection() as connection:
        rule = connection.execute("SELECT category_name FROM merchant_rules WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
    assert rule["category_name"] == "Food"


def test_user_merchant_rule_precedes_global_categorization():
    user_id = _user()
    db.create_merchant_rule(user_id, "campus canteen", "Education")
    result = ingest_with_adapter(
        CSVAdapter(),
        b"date,description,amount,mode,type\n2026-08-15,CAMPUS CANTEEN LUNCH,80,UPI,DEBIT\n",
        user_id,
        idempotency_key="rule-precedence-1",
    )
    assert result["aggregate"]["categories"]["Education"] == 80
    assert result["aggregate"]["classification_metadata"][0]["classification_method"] == "user_rule"


def test_processing_checkpoint_is_persisted():
    user_id = _user()
    import_record = db.create_import(user_id, "CSV")
    job_id = db.create_processing_job(user_id, import_record["id"], "CSV_INGESTION")
    db.update_processing_checkpoint(job_id, user_id, "NORMALIZATION_STARTED", progress={"rows": 2})
    with get_sqlite_connection() as connection:
        row = connection.execute("SELECT status, progress FROM processing_jobs WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()
    assert row["status"] == "RUNNING"
    assert json.loads(row["progress"])["NORMALIZATION_STARTED"]["rows"] == 2


def test_setu_adapter_creates_owned_canonical_transaction():
    user_id = _user()
    payload = {"fips": [{"accounts": [{"data": {"account": {"transactions": {"transaction": [{
        "amount": "125.00",
        "mode": "UPI",
        "narration": "TEST GROCERY",
        "valueDate": "2026-08-15T10:00:00Z",
        "type": "DEBIT",
    }]}}}}]}]}
    result = ingest_with_adapter(SetuAdapter(), payload, user_id, idempotency_key="session:test-1")
    assert result["status"] == "processed"
    assert db.list_imports(user_id)[0]["source"] == "SETU"
    assert db.list_transactions(user_id)[0]["source"] == "SETU"
