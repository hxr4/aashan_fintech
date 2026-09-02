"""Ownership is re-derived from the token on every access, and writes are allow-listed."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import db
from app.main import app
from app.models.ingestion import TransactionReviewRequest
from app.services import ledger
from app.services.ingestion import RowsAdapter
from app.services.ingestion.service import ingest_with_adapter
from app.services.review import review_transaction

SECRET = "authz-test-secret-0123456789012345"


@pytest.fixture
def authenticated(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "supabase_jwt_issuer", "https://identity.example.test/auth/v1")
    monkeypatch.setattr(settings, "supabase_jwt_audience", "authenticated")
    monkeypatch.setattr(settings, "rate_limit_enabled", False)


def _token(user_id: str, **overrides) -> str:
    claims = {
        "sub": user_id,
        "aud": "authenticated",
        "iss": "https://identity.example.test/auth/v1",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _headers(user_id: str) -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _seed(user_id: str) -> dict:
    ingest_with_adapter(
        RowsAdapter("SMS"),
        [{"date": "2026-08-01", "description": "SWIGGY ORDER", "amount": 500,
          "mode": "UPI", "transaction_type": "DEBIT"}],
        user_id,
    )
    return db.list_transactions(user_id, "CONFIRMED")[0]


OWNED_PATHS = [
    "/api/transactions", "/api/imports", "/api/transaction-candidates",
    "/api/review-queue", "/api/coverage", "/api/jobs", "/api/budgets",
    "/api/dashboard/summary", "/api/dashboard/categories",
]


def test_every_owned_route_refuses_an_anonymous_caller(authenticated):
    with TestClient(app) as client:
        for path in OWNED_PATHS:
            assert client.get(path).status_code == 401, path


def test_a_forged_token_is_refused(authenticated):
    forged = jwt.encode(
        {"sub": "attacker", "aud": "authenticated", "iss": "https://identity.example.test/auth/v1",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "the-wrong-signing-key-000000000000", algorithm="HS256",
    )
    with TestClient(app) as client:
        assert client.get("/api/transactions", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_an_expired_token_is_refused(authenticated):
    stale = _token("user-a", exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    with TestClient(app) as client:
        assert client.get("/api/transactions", headers={"Authorization": f"Bearer {stale}"}).status_code == 401


def test_one_user_cannot_read_or_touch_another_users_transaction(authenticated):
    owner = "owner-" + uuid.uuid4().hex
    intruder = "intruder-" + uuid.uuid4().hex
    transaction = _seed(owner)

    with TestClient(app) as client:
        assert len(client.get("/api/transactions", headers=_headers(owner)).json()["transactions"]) == 1
        assert client.get("/api/transactions", headers=_headers(intruder)).json()["transactions"] == []

        # Guessing the id is not enough: ownership is re-checked per record.
        assert client.get(f"/api/transactions/{transaction['id']}/observations",
                          headers=_headers(intruder)).status_code == 404
        assert client.post(f"/api/transactions/{transaction['id']}/review",
                           json={"action": "REJECT"}, headers=_headers(intruder)).status_code == 404

    # The owner's row is untouched.
    assert ledger.read_aggregate(owner)["total_spending"] == 500


def test_a_client_cannot_smuggle_extra_fields_into_a_review(authenticated):
    owner = "owner-" + uuid.uuid4().hex
    transaction = _seed(owner)
    with TestClient(app) as client:
        response = client.post(
            f"/api/transactions/{transaction['id']}/review",
            json={"action": "APPROVE", "user_id": "somebody-else", "amount": 1},
            headers=_headers(owner),
        )
    assert response.status_code == 422


def test_an_amount_cannot_be_changed_without_an_explicit_edit():
    owner = "owner-" + uuid.uuid4().hex
    import_record = db.create_import(owner, "MANUAL")
    from app.models.ingestion import NormalizedTransactionInput

    item = NormalizedTransactionInput(
        transaction_at=datetime(2026, 8, 15, tzinfo=timezone.utc), amount=500.0,
        direction="DEBIT", transaction_type="DEBIT", description="RENT",
        mode="UPI", source_type="MANUAL",
    )
    candidate_id = db.create_candidate(owner, import_record["id"], item, "Other", "fallback", 0.0,
                                       review_status="PENDING_REVIEW", transaction_status="PENDING_REVIEW")
    from app.services.review import review_candidate

    review_candidate(owner, candidate_id, TransactionReviewRequest(action="APPROVE", amount=999999))
    # APPROVE is not an amount correction, so the original figure stands.
    assert ledger.read_aggregate(owner)["total_spending"] == 500


def test_status_filters_are_validated_rather_than_silently_empty(authenticated):
    owner = "owner-" + uuid.uuid4().hex
    _seed(owner)
    with TestClient(app) as client:
        assert client.get("/api/transactions?status=NONSENSE", headers=_headers(owner)).status_code == 422
        assert client.get("/api/transactions?status=CONFIRMED", headers=_headers(owner)).status_code == 200


def test_oversized_and_malformed_input_is_rejected(authenticated):
    owner = "owner-" + uuid.uuid4().hex
    with TestClient(app) as client:
        assert client.post("/api/ingest/sms", json={"sms_text": "x" * 5000},
                           headers=_headers(owner)).status_code == 422
        assert client.post("/api/ingest/sms", json={"sms_text": "Rs 100 debited", "extra": "field"},
                           headers=_headers(owner)).status_code == 422
        assert client.post("/api/insights/query", json={"question": ""},
                           headers=_headers(owner)).status_code == 422
