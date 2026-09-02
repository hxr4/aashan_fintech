"""Nobody writes to a ledger by knowing a consent id."""

import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import LOCAL_USER_ID
from app.config import settings
from app.database import db
from app.main import app
from app.services.webhook_auth import sign

SECRET = "test-webhook-secret-0123456789abcdef"
TOKEN = "test-webhook-token-0123456789abcdef"


def _payload() -> dict:
    return {
        "type": "FI_DATA_READY",
        "consentId": "consent-" + uuid.uuid4().hex,
        "notificationId": "notification-" + uuid.uuid4().hex,
        "status": "COMPLETED",
        "fiData": [{"data": [{"decryptedFI": {"account": {"transactions": {"transaction": [{
            "amount": "5000", "mode": "CARD", "narration": "ATTACKER INJECTED",
            "valueDate": "2026-08-16T10:00:00Z", "type": "DEBIT",
        }]}}}}]}],
    }


@pytest.fixture
def signed_mode(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "aa_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "aa_webhook_token", "")
    return SECRET


def test_an_unsigned_webhook_is_refused(signed_mode):
    body = json.dumps(_payload()).encode()
    with TestClient(app) as client:
        response = client.post("/api/webhooks/setu", content=body,
                               headers={"Content-Type": "application/json"})
    assert response.status_code == 401
    # No transaction was written for anyone.
    assert db.list_transactions(LOCAL_USER_ID, None) == []


def test_a_forged_signature_is_refused(signed_mode):
    body = json.dumps(_payload()).encode()
    forged = f"t={int(time.time())},v1={'a' * 64}"
    with TestClient(app) as client:
        response = client.post("/api/webhooks/setu", content=body,
                               headers={"Content-Type": "application/json", "X-Aashan-Signature": forged})
    assert response.status_code == 401
    assert db.list_transactions(LOCAL_USER_ID, None) == []


def test_a_signature_for_a_different_body_is_refused(signed_mode):
    """Signing one payload does not authorise a swapped one."""
    innocent = json.dumps({"type": "CONSENT_STATUS_UPDATE", "consentId": "c1"}).encode()
    header = sign(SECRET, innocent)
    with TestClient(app) as client:
        response = client.post("/api/webhooks/setu", content=json.dumps(_payload()).encode(),
                               headers={"Content-Type": "application/json", "X-Aashan-Signature": header})
    assert response.status_code == 401
    assert db.list_transactions(LOCAL_USER_ID, None) == []


def test_a_replayed_old_signature_is_refused(signed_mode):
    body = json.dumps(_payload()).encode()
    stale = sign(SECRET, body, timestamp=int(time.time()) - 3600)
    with TestClient(app) as client:
        response = client.post("/api/webhooks/setu", content=body,
                               headers={"Content-Type": "application/json", "X-Aashan-Signature": stale})
    assert response.status_code == 401


def test_a_correctly_signed_webhook_is_accepted(signed_mode, monkeypatch):
    from tests.test_setu import _configure_setu

    _configure_setu(monkeypatch)
    monkeypatch.setattr(settings, "aa_webhook_secret", SECRET)
    body = json.dumps(_payload()).encode()
    with TestClient(app) as client:
        response = client.post("/api/webhooks/setu", content=body,
                               headers={"Content-Type": "application/json",
                                        "X-Aashan-Signature": sign(SECRET, body)})
    assert response.status_code == 200
    assert response.json()["processed"] is True
    assert len(db.list_transactions(LOCAL_USER_ID, "CONFIRMED")) == 1


def test_a_bearer_token_deployment_accepts_only_the_right_token(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "aa_webhook_secret", "")
    monkeypatch.setattr(settings, "aa_webhook_token", TOKEN)
    body = json.dumps({"type": "CONSENT_STATUS_UPDATE", "consentId": "c-" + uuid.uuid4().hex}).encode()
    with TestClient(app) as client:
        wrong = client.post("/api/webhooks/setu", content=body,
                            headers={"Content-Type": "application/json", "Authorization": "Bearer nope"})
        right = client.post("/api/webhooks/setu", content=body,
                            headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"})
    assert wrong.status_code == 401
    assert right.status_code == 200


def test_it_fails_closed_when_nothing_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "aa_webhook_secret", "")
    monkeypatch.setattr(settings, "aa_webhook_token", "")
    with TestClient(app) as client:
        response = client.post("/api/webhooks/setu", json={"type": "CONSENT_STATUS_UPDATE", "consentId": "c"})
    # Refused, not silently accepted, when the operator forgot to configure it.
    assert response.status_code == 503


def test_an_oversized_webhook_is_refused(signed_mode):
    body = b'{"type":"FI_DATA_READY","consentId":"c","pad":"' + b"x" * (2 * 1024 * 1024) + b'"}'
    with TestClient(app) as client:
        response = client.post("/api/webhooks/setu", content=body,
                               headers={"Content-Type": "application/json",
                                        "X-Aashan-Signature": sign(SECRET, body)})
    assert response.status_code == 413
