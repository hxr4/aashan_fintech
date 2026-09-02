import json
import uuid

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.aa_client import build_consent_payload
from app.services.normalizer import normalize_transaction
from app.services.setu_mapper import flatten_setu_transactions
from app.services.webhook_auth import sign

WEBHOOK_SECRET = "setu-test-webhook-secret-0123456789"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = httpx.Request("POST", "https://setu.test")
            response = httpx.Response(self.status_code, request=request, text=self.text)
            raise httpx.HTTPStatusError("fake Setu error", request=request, response=response)

    def json(self):
        return self._payload


class FakeAsyncClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append(("POST", url, json, headers))
        if url.endswith("/v1/users/login"):
            return FakeResponse({"access_token": "test-token", "expires_in": 300})
        if url.endswith("/v2/consents"):
            return FakeResponse({"id": "consent-test", "url": "https://fiu-sandbox.setu.co/v2/consents/webview/consent-test", "status": "PENDING"})
        if url.endswith("/sessions"):
            return FakeResponse({"id": "session-test", "status": "PENDING", "consentId": "consent-test"})
        raise AssertionError("Unexpected fake Setu POST: " + url)

    async def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, kwargs.get("json"), headers))
        if method == "POST" and url.endswith("/v2/consents"):
            return FakeResponse({"id": "consent-test", "url": "https://fiu-sandbox.setu.co/v2/consents/webview/consent-test", "status": "PENDING"})
        if method == "POST" and url.endswith("/sessions"):
            return FakeResponse({"id": "session-test", "status": "PENDING", "consentId": "consent-test"})
        if url.endswith("/v2/consents/consent-test"):
            return FakeResponse({"id": "consent-test", "status": "ACTIVE"})
        if "/sessions/" in url:
            return FakeResponse({
                "status": "COMPLETED",
                "fips": [{
                    "accounts": [{
                        "data": {"account": {"transactions": {"transaction": [{
                            "amount": "450.00",
                            "mode": "UPI",
                            "narration": "UPI/CR/SWIGGY",
                            "transactionTimestamp": "2026-08-15T10:00:00Z",
                            "type": "CREDIT",
                            "valueDate": "2026-08-15T10:00:00Z",
                        }]}}}
                    }]
                }],
            })
        raise AssertionError("Unexpected fake Setu request: " + url)


def _configure_setu(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "setu_base_url", "https://fiu-sandbox.setu.co")
    monkeypatch.setattr(settings, "setu_auth_base_url", "https://accountservice.setu.co")
    monkeypatch.setattr(settings, "setu_client_id", "client-id")
    monkeypatch.setattr(settings, "setu_client_secret", "client-secret")
    monkeypatch.setattr(settings, "setu_product_instance_id", "product-instance")
    monkeypatch.setattr(settings, "redirect_url", "https://example.test/api/aa/callback")
    monkeypatch.setattr(settings, "setu_auto_fetch", False)
    monkeypatch.setattr(settings, "aa_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "aa_webhook_token", "")
    FakeAsyncClient.calls = []
    monkeypatch.setattr("app.services.aa_client.httpx.AsyncClient", FakeAsyncClient)


def _post_signed(client, payload):
    """A real provider signs its callbacks; so do the tests."""
    body = json.dumps(payload).encode()
    return client.post(
        "/api/webhooks/setu",
        content=body,
        headers={"Content-Type": "application/json", "X-Aashan-Signature": sign(WEBHOOK_SECRET, body)},
    )


def test_consent_payload_construction():
    payload = build_consent_payload({
        "purpose": "Personal finance spending insights",
        "purpose_code": "102",
        "mobile_number": "9999999999",
        "data_range_from": "2026-06-01T00:00:00Z",
        "data_range_to": "2026-08-31T23:59:59Z",
        "fi_types": ["DEPOSIT"],
        "consent_types": ["TRANSACTIONS"],
    }, "https://example.test/api/aa/callback")

    assert payload["vua"] == "9999999999"
    assert payload["fiTypes"] == ["DEPOSIT"]
    assert payload["consentTypes"] == ["TRANSACTIONS"]
    assert payload["dataRange"]["from"] == "2026-06-01T00:00:00Z"
    assert payload["purpose"] == {
        "category": {"type": "string"},
        "code": "102",
        "refUri": "https://api.rebit.org.in/aa/purpose/102.xml",
        "text": "Personal finance spending insights",
    }
    assert payload["frequency"] == {"unit": "DAY", "value": 1}
    assert payload["redirectUrl"] == "https://example.test/api/aa/callback"


def test_real_consent_and_status_routes_use_mocked_setu(monkeypatch):
    _configure_setu(monkeypatch)
    with TestClient(app) as client:
        created = client.post("/api/aa/consent", json={"mobile_number": "9999999999"})
        assert created.status_code == 200
        assert created.json()["consent_id"] == "consent-test"
        assert created.json()["url"].startswith("https://fiu-sandbox.setu.co")

        consent_call = next(call for call in FakeAsyncClient.calls if call[1].endswith("/v2/consents"))
        assert consent_call[2]["redirectUrl"] == "https://example.test/api/aa/callback"
        assert consent_call[2]["consentTypes"] == ["TRANSACTIONS"]

        status = client.get("/api/aa/consent/consent-test")
        assert status.status_code == 200
        assert status.json()["setu"]["status"] == "ACTIVE"
        assert status.json()["data_fetched"] is False


def test_callback_success_and_error_are_explicit(monkeypatch):
    _configure_setu(monkeypatch)
    with TestClient(app) as client:
        success = client.get("/api/aa/callback?success=true&id=consent-success")
        assert success.status_code == 200
        assert success.json()["status"] == "approved_pending_processing"
        assert success.json()["data_fetched"] is False

        error = client.get("/api/aa/callback?success=false&id=consent-error&errorcode=UserRejected&errormsg=no")
        assert error.status_code == 200
        assert error.json()["status"] == "rejected"
        assert error.json()["error"]["code"] == "UserRejected"
        assert error.json()["data_fetched"] is False


def test_flatten_and_normalize_nested_setu_transaction():
    payload = {
        "fips": [{"accounts": [{"data": {"account": {"transactions": {"transaction": [{
            "amount": "1,250.50",
            "mode": "NEFT",
            "narration": "SALARY CREDIT",
            "transactionTimestamp": "2026-08-15T10:00:00Z",
            "type": "CREDIT",
        }]}}}}]}],
    }
    rows = flatten_setu_transactions(payload)
    assert rows == [{
        "date": "2026-08-15T10:00:00Z",
        "description": "SALARY CREDIT",
        "amount": "1,250.50",
        "mode": "NEFT",
        "transaction_type": "CREDIT",
    }]
    normalized = normalize_transaction(rows[0])
    assert normalized.transaction_type == "CREDIT"
    assert normalized.amount == 1250.50
    assert normalized.description == "SALARY CREDIT"


def test_setu_session_webhook_creates_canonical_transactions_and_is_idempotent(monkeypatch):
    _configure_setu(monkeypatch)
    from app.auth import LOCAL_USER_ID
    from app.database import db
    from app.services import ledger

    consent_id = "consent-" + uuid.uuid4().hex
    session_id = "session-" + uuid.uuid4().hex
    payload = {
        "type": "SESSION_STATUS_UPDATE",
        "consentId": consent_id,
        "dataSessionId": session_id,
        "notificationId": "notification-" + uuid.uuid4().hex,
        "data": {"status": "COMPLETED"},
        "success": True,
    }

    with TestClient(app) as client:
        first = _post_signed(client, payload)
        second = _post_signed(client, payload)

    assert first.status_code == 200
    assert first.json()["processed"] is True
    assert second.status_code == 200
    assert second.json()["duplicate"] is True

    # Assert the outcome rather than that an internal function was called:
    # the fetched FI credit of 450 became exactly one canonical transaction.
    rows = db.list_transactions(LOCAL_USER_ID, "CONFIRMED")
    assert len(rows) == 1
    assert rows[0]["direction"] == "CREDIT"
    assert float(rows[0]["amount"]) == 450.0
    aggregate = ledger.read_aggregate(LOCAL_USER_ID)
    assert aggregate["total_credit"] == 450
    assert aggregate["total_spending"] == 0


def test_fi_data_ready_flattens_embedded_payload_and_processes_once(monkeypatch):
    _configure_setu(monkeypatch)
    from app.auth import LOCAL_USER_ID
    from app.database import db
    from app.services import ledger

    consent_id = "consent-" + uuid.uuid4().hex
    notification_id = "notification-" + uuid.uuid4().hex
    payload = {
        "type": "FI_DATA_READY",
        "consentId": consent_id,
        "notificationId": notification_id,
        "status": "COMPLETED",
        "fiData": [{"data": [{"decryptedFI": {"account": {"transactions": {"transaction": [{
            "amount": "100",
            "mode": "CARD",
            "narration": "GROCERY",
            "valueDate": "2026-08-16T10:00:00Z",
            "type": "DEBIT",
        }]}}}}]}],
    }
    with TestClient(app) as client:
        first = _post_signed(client, payload)
        second = _post_signed(client, payload)
    assert first.status_code == 200
    assert first.json()["processed"] is True
    assert second.json()["duplicate"] is True

    rows = db.list_transactions(LOCAL_USER_ID, "CONFIRMED")
    assert len(rows) == 1
    assert rows[0]["direction"] == "DEBIT"
    assert ledger.read_aggregate(LOCAL_USER_ID)["total_spending"] == 100
