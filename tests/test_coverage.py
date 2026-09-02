"""No rate without the days it was divided by."""

import uuid

from app.database import db
from app.services import ledger
from app.services.ingestion import CSVAdapter, RowsAdapter
from app.services.ingestion.service import ingest_with_adapter


def _user() -> str:
    return "cov-" + uuid.uuid4().hex


def _rows(days, amount=100):
    return [
        {"date": day, "description": f"SWIGGY {day}", "amount": amount, "mode": "UPI", "transaction_type": "DEBIT"}
        for day in days
    ]


def test_every_rate_states_its_denominator():
    user_id = _user()
    ingest_with_adapter(RowsAdapter("SMS"), _rows(["2026-08-01", "2026-08-02", "2026-08-03"]), user_id)
    rates = ledger.read_aggregate(user_id)["rates"]
    assert rates["basis"] == "covered_days"
    assert rates["covered_days"] == 3
    assert rates["spending_per_covered_day"] == 100.0
    assert "3 covered day(s)" in rates["explanation"]


def test_a_gap_is_reported_rather_than_averaged_away():
    """The spreadsheet's shape: two blocks with a hole between them."""
    user_id = _user()
    ingest_with_adapter(RowsAdapter("SMS"), _rows(["2026-08-01", "2026-08-02"]), user_id)
    ingest_with_adapter(RowsAdapter("SMS"), _rows(["2026-08-20", "2026-08-21"]), user_id)

    coverage = ledger.read_aggregate(user_id)["coverage"]
    assert coverage["covered_days"] == 4
    assert coverage["first_covered"] == "2026-08-01"
    assert coverage["last_covered"] == "2026-08-21"
    assert coverage["gaps"] == [{"from": "2026-08-03", "to": "2026-08-19", "days": 17}]

    rates = ledger.read_aggregate(user_id)["rates"]
    # 400 over 4 covered days, not over the 21-day span.
    assert rates["spending_per_covered_day"] == 100.0
    assert rates["uncovered_days_in_period"] == 17
    assert "17 day(s)" in rates["explanation"]


def test_coverage_is_tracked_per_source():
    user_id = _user()
    ingest_with_adapter(RowsAdapter("SMS"), _rows(["2026-08-01", "2026-08-10"]), user_id)
    ingest_with_adapter(
        CSVAdapter(),
        b"date,description,amount,mode,type\n2026-09-01,SWIGGY,100,UPI,DEBIT\n",
        user_id,
        idempotency_key="sep",
    )
    sources = {item["source"]: item for item in ledger.read_aggregate(user_id)["coverage"]["sources"]}
    assert set(sources) == {"SMS", "CSV"}
    assert sources["SMS"]["from"] == "2026-08-01"
    assert sources["SMS"]["to"] == "2026-08-10"
    assert sources["CSV"]["covered_days"] == 1


def test_no_coverage_refuses_to_state_a_rate():
    user_id = _user()
    rates = ledger.read_aggregate(user_id)["rates"]
    assert rates["basis"] == "no_coverage"
    assert rates["spending_per_covered_day"] is None
    assert rates["projected_monthly"] is None
