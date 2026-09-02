from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import uuid4


def generate_mock_transactions(count: int = 75) -> List[Dict[str, Any]]:
    """Return clearly labelled, deterministic demo data; never real bank data."""
    templates = [
        ("UPI-SWIGGY-ORDER", 450, "UPI", "DEBIT"), ("UPI-ZOMATO-ORDER", 680, "UPI", "DEBIT"),
        ("UPI-UBER-INDIA", 220, "UPI", "DEBIT"), ("OLA-CABS-RIDE", 340, "UPI", "DEBIT"),
        ("AMAZON INDIA", 1200, "CARD", "DEBIT"), ("FLIPKART ONLINE", 890, "CARD", "DEBIT"),
        ("JIO RECHARGE", 799, "UPI", "DEBIT"), ("AIRTEL BROADBAND", 999, "UPI", "DEBIT"),
        ("NETFLIX.COM", 649, "CARD", "DEBIT"), ("SPOTIFY PREMIUM", 119, "CARD", "DEBIT"),
        ("APOLLO PHARMACY", 560, "CARD", "DEBIT"), ("UDemy COURSE", 1500, "CARD", "DEBIT"),
        ("SALARY CREDIT", 45000, "NEFT", "CREDIT"), ("UPI-SWIGGY-LARGE-ORDER", 2400, "UPI", "DEBIT"),
        ("RESTAURANT DINNER", 1750, "CARD", "DEBIT"),
    ]
    start = datetime(2026, 6, 1)
    transactions = []
    for index in range(count):
        description, amount, mode, transaction_type = templates[index % len(templates)]
        date = start + timedelta(days=(index * 2) % 92)
        multiplier = 1 + ((index % 4) * 0.05)
        transactions.append({
            "date": date.strftime("%Y-%m-%d"),
            "description": "MOCK / DEMO DATA - " + description,
            "amount": round(amount * multiplier, 2),
            "mode": mode,
            "transaction_type": transaction_type,
        })
    # One intentional demo outlier makes the anomaly panel useful during a hackathon demo.
    if transactions:
        transactions[-1].update({
            "description": "MOCK / DEMO DATA - FLIGHT BOOKING OUTLIER",
            "amount": 15000,
            "mode": "CARD",
            "transaction_type": "DEBIT",
        })
    return transactions


class MockAAProvider:
    source_label = "MOCK AA DATA"

    def __init__(self) -> None:
        self.consents = {}
        self.sessions = {}

    async def create_consent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        consent_id = str(uuid4())
        self.consents[consent_id] = {"id": consent_id, "status": "PENDING", "payload": payload}
        return {"id": consent_id, "status": "PENDING", "url": "/api/aa/mock/approve?consent_id=" + consent_id, "source": self.source_label}

    async def get_consent_status(self, consent_id: str) -> Dict[str, Any]:
        if consent_id not in self.consents:
            raise ValueError("Consent not found")
        return self.consents[consent_id]

    async def approve_consent(self, consent_id: str) -> Dict[str, Any]:
        status = await self.get_consent_status(consent_id)
        status.update({"status": "ACTIVE", "account_linked": True})
        return status

    async def create_data_session(self, consent_id: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        status = await self.get_consent_status(consent_id)
        if status["status"] != "ACTIVE":
            raise ValueError("Consent must be ACTIVE before creating a data session")
        session_id = str(uuid4())
        self.sessions[session_id] = {"id": session_id, "consentId": consent_id, "status": "READY"}
        return self.sessions[session_id]

    async def fetch_data(self, session_id: str) -> List[Dict[str, Any]]:
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError("Data session not found")
        return generate_mock_transactions()
