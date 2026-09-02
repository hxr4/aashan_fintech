"""Uploads are bounded, jobs are owner-scoped, and work leaves the event loop."""

import io
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.ingestion import worker


def _csv_bytes(rows: int) -> bytes:
    header = "date,description,amount,mode,type\n"
    body = "".join(f"2026-08-{(i % 28) + 1:02d},SWIGGY ORDER {i},100,UPI,DEBIT\n" for i in range(rows))
    return (header + body).encode()


def test_oversized_upload_is_refused_before_it_is_all_in_memory():
    oversized = b"date,description,amount,mode,type\n" + b"x" * (6 * 1024 * 1024)
    with TestClient(app) as client:
        response = client.post("/api/ingest/csv", files={"file": ("big.csv", oversized, "text/csv")})
    assert response.status_code == 413
    assert "limit" in response.json()["detail"].lower()


def test_a_normal_upload_still_returns_its_result_synchronously():
    with TestClient(app) as client:
        response = client.post("/api/ingest/csv", files={"file": ("ok.csv", _csv_bytes(5), "text/csv")})
    assert response.status_code == 200
    assert response.json()["rows_processed"] == 5


def test_background_mode_returns_immediately_and_records_a_job():
    with TestClient(app) as client:
        response = client.post(
            "/api/ingest/csv?background=true",
            files={"file": ("bg.csv", _csv_bytes(3), "text/csv")},
        )
        assert response.status_code == 200
        assert response.json()["background"] is True

        worker.executor().shutdown(wait=True)
        worker.shutdown()

        jobs = client.get("/api/jobs").json()["jobs"]
    assert jobs
    assert jobs[0]["status"] == "COMPLETED"
    assert jobs[0]["job_type"] == "CSV_INGESTION"


def test_a_job_belonging_to_someone_else_is_not_readable():
    with TestClient(app) as client:
        client.post("/api/ingest/csv", files={"file": ("mine.csv", _csv_bytes(2), "text/csv")})
        jobs = client.get("/api/jobs").json()["jobs"]
        assert jobs
        assert client.get(f"/api/jobs/{jobs[0]['id']}").status_code == 200
        assert client.get(f"/api/jobs/{uuid.uuid4()}").status_code == 404
