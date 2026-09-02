"""Exact arithmetic and one timezone."""

import uuid
from datetime import datetime, timezone

from app.services import ledger
from app.services.clock import IST, to_ist
from app.services.ingestion import RowsAdapter
from app.services.ingestion.service import ingest_with_adapter
from app.services.money import as_float, total


def _user() -> str:
    return "money-" + uuid.uuid4().hex


def test_decimal_summation_does_not_drift():
    values = [974.71, 0.1, 0.2] * 2000
    assert sum(values) != 1950020.0          # plain float addition drifts
    assert as_float(total(values)) == 1950020.0


def test_many_small_amounts_total_exactly():
    """The real shape of this product: dozens of Rs20-Rs110 rows."""
    user_id = _user()
    rows = [
        {"date": f"2026-08-{day:02d}", "description": "CHAI STALL", "amount": 20.10,
         "mode": "UPI", "transaction_type": "DEBIT"}
        for day in range(1, 31)
    ]
    ingest_with_adapter(RowsAdapter("SMS"), rows, user_id)
    assert ledger.read_aggregate(user_id)["total_spending"] == 603.00


def test_naive_source_dates_are_treated_as_indian_local_time():
    moment = to_ist("2026-08-31T23:40:00")
    assert moment.tzinfo is not None
    assert moment.utcoffset().total_seconds() == 5.5 * 3600
    assert moment.strftime("%Y-%m") == "2026-08"


def test_a_late_night_transaction_stays_in_its_own_month():
    user_id = _user()
    ingest_with_adapter(
        RowsAdapter("SMS"),
        [{"date": "2026-08-31T23:40:00", "description": "SWIGGY ORDER", "amount": 500,
          "mode": "UPI", "transaction_type": "DEBIT"}],
        user_id,
    )
    # Naive input is Indian wall-clock, so this is August spending, not September.
    assert ledger.read_aggregate(user_id)["monthly"] == {"2026-08": 500.0}


def test_utc_input_is_converted_not_reinterpreted():
    aware = datetime(2026, 8, 15, 18, 30, tzinfo=timezone.utc)
    assert to_ist(aware).strftime("%Y-%m-%d %H:%M") == "2026-08-16 00:00"
