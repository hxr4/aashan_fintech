from fastapi.testclient import TestClient

from app.main import app


def test_demo_and_dashboard():
    with TestClient(app) as client:
        demo = client.post("/api/demo/run")
        assert demo.status_code == 200
        assert demo.json()["transactions_processed"] == 75
        assert demo.json()["raw_transactions_persisted"] is False
        summary = client.get("/api/dashboard/summary")
        assert summary.status_code == 200
        assert summary.json()["total_spending"] > 0


def test_mock_consent_flow():
    with TestClient(app) as client:
        consent = client.post("/api/aa/mock/consent", json={}).json()
        assert client.post("/api/aa/mock/approve", params={"consent_id": consent["id"]}).status_code == 200
        fetched = client.post("/api/aa/mock/fetch", params={"consent_id": consent["id"]})
        assert fetched.status_code == 200
        assert fetched.json()["source"] == "MOCK AA DATA"

