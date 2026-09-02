from fastapi.testclient import TestClient
import numpy as np

from app.main import app
from app.services.categorizer import Categorizer
import app.services.pipeline as pipeline


def test_sms_ingestion_does_not_return_sms_text():
    with TestClient(app) as client:
        response = client.post("/api/ingest/sms", json={"sms_text": "Rs. 450 debited via UPI to SWIGGY"})
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Food"
    assert "sms_text" not in body


class FakeEmbeddingModel:
    def encode(self, texts, **kwargs):
        vectors = []
        for text in texts:
            text = text.lower()
            if any(word in text for word in ("food", "cafe", "restaurant", "swiggy", "zomato")):
                vectors.append([1.0, 0.0, 0.0])
            elif any(word in text for word in ("uber", "ola", "taxi", "metro", "train")):
                vectors.append([0.0, 1.0, 0.0])
            elif any(word in text for word in ("amazon", "flipkart", "shopping", "retail")):
                vectors.append([0.0, 0.0, 1.0])
            else:
                vectors.append([0.0, 0.0, 0.0])
        return np.asarray(vectors)


def test_csv_ingestion(monkeypatch):
    monkeypatch.setattr(pipeline, "Categorizer", lambda: Categorizer(embedding_model=FakeEmbeddingModel()))
    csv = "Date,Description,Amount,Mode,Type\n2026-08-01,UPI-SWIGGY,450,UPI,DEBIT\n2026-08-02,UNKNOWN CAFE KOCHI,540,UPI,DEBIT\n2026-08-03,SALARY CREDIT,45000,NEFT,CREDIT\n"
    with TestClient(app) as client:
        response = client.post("/api/ingest/csv", files={"file": ("demo.csv", csv, "text/csv")})
    assert response.status_code == 200
    body = response.json()
    assert body["rows_processed"] == 3
    assert body["aggregate"]["total_spending"] == 990
    assert body["aggregate"]["total_credit"] == 45000
    assert body["aggregate"]["net_cash_flow"] == 44010
    metadata = body["aggregate"]["classification_metadata"]
    assert metadata[0]["classification_method"] == "merchant_rule"
    assert metadata[1]["classification_method"] == "embedding_similarity"
    assert metadata[1]["category"] == "Food"
    assert metadata[2]["category"] == "Salary"
    assert metadata[2]["transaction_type"] == "CREDIT"


def test_exact_csv_credit_regression(monkeypatch):
    monkeypatch.setattr(pipeline, "Categorizer", lambda: Categorizer(embedding_model=FakeEmbeddingModel()))
    csv = """date,description,amount,mode,type
2026-08-01,UPI-SWIGGY-123,450,UPI,DEBIT
2026-08-02,UBER INDIA,220,UPI,DEBIT
2026-08-03,AMAZON INDIA,1200,CARD,DEBIT
2026-08-04,JIO RECHARGE,799,UPI,DEBIT
2026-08-05,LOCAL FOOD COURT,650,UPI,DEBIT
2026-08-06,NETFLIX.COM,649,CARD,DEBIT
2026-08-07,APOLLO PHARMACY,875,UPI,DEBIT
2026-08-08,IRCTC TRAIN TICKET,1450,CARD,DEBIT
2026-08-09,SPOTIFY PREMIUM,119,UPI,DEBIT
2026-08-10,FLIPKART ONLINE,2399,CARD,DEBIT
2026-08-11,SWIGGY INSTAMART,780,UPI,DEBIT
2026-08-12,OLA CABS,310,UPI,DEBIT
2026-08-13,COLLEGE FEE PAYMENT,12500,NEFT,DEBIT
2026-08-14,ZUDIO RETAIL,1600,CARD,DEBIT
2026-08-15,SALARY CREDIT,45000,NEFT,CREDIT
2026-08-16,RESTAURANT XYZ,980,UPI,DEBIT
2026-08-17,AIRTEL POSTPAID,699,UPI,DEBIT
2026-08-18,UNKNOWN CAFE KOCHI,540,UPI,DEBIT
"""
    with TestClient(app) as client:
        response = client.post("/api/ingest/csv", files={"file": ("exact.csv", csv, "text/csv")})
    assert response.status_code == 200
    aggregate = response.json()["aggregate"]
    salary = aggregate["classification_metadata"][14]
    assert salary["category"] == "Salary"
    assert salary["transaction_type"] == "CREDIT"
    assert aggregate["total_credit"] == 45000
    assert aggregate["total_debit"] == 26220
    assert aggregate["total_spending"] == 26220
    assert aggregate["net_cash_flow"] == 18780
    assert "Salary" not in aggregate["categories"]
    assert "Salary" not in aggregate["category_percentages"]
    assert aggregate["monthly"] == {"2026-08": 26220}

    summary = client.get("/api/dashboard/summary").json()
    assert summary["total_debit"] == 26220
    assert summary["total_spending"] == 26220
    assert summary["total_credit"] == 45000
    assert summary["net_cash_flow"] == 18780
    assert client.get("/api/dashboard/categories").json()["categories"].get("Salary") is None
    assert client.get("/api/dashboard/monthly").json()["monthly"] == {"2026-08": 26220}
