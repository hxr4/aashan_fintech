"""The privacy statement must be falsifiable, and deletion must actually delete."""

import uuid

from app.database import db
from app.database.db import privacy_database_status
from app.services import ledger
from app.services.ingestion import RowsAdapter
from app.services.ingestion.service import ingest_with_adapter


def _user() -> str:
    return "privacy-" + uuid.uuid4().hex


def _seed(user_id: str, rows: int = 3) -> None:
    ingest_with_adapter(
        RowsAdapter("SMS"),
        [{"date": f"2026-08-{i + 1:02d}", "description": f"SWIGGY ORDER {i}", "amount": 100,
          "mode": "UPI", "transaction_type": "DEBIT"} for i in range(rows)],
        user_id,
    )


def test_the_privacy_statement_admits_what_is_actually_stored():
    """The old check looked for three tables that never existed, so it could not fail."""
    user_id = _user()
    _seed(user_id)
    status = privacy_database_status(user_id)

    assert status["retained"]["canonical_transactions"] == 3
    assert status["retained"]["source_observations"] == 3
    # Descriptions are stored. Saying otherwise, as the product used to, was false.
    assert status["transaction_descriptions_stored"] is True
    assert status["descriptions_stored_count"] == 3
    assert "discarded" in status["statement"].lower()


def test_a_fresh_account_reports_nothing_retained():
    status = privacy_database_status(_user())
    assert status["retained"]["canonical_transactions"] == 0
    assert status["transaction_descriptions_stored"] is False


def test_export_returns_everything_held():
    from app.api.auth import _export

    user_id = _user()
    _seed(user_id)
    export = _export(user_id)
    assert len(export["transactions"]) == 3
    assert len(export["observations"]) == 3
    assert export["coverage"]
    assert export["aggregate"]["total_spending"] == 300


def test_deletion_removes_every_trace_and_is_audited():
    user_id = _user()
    _seed(user_id)
    assert ledger.read_aggregate(user_id)["total_spending"] == 300

    removed = db.purge_user(user_id)
    db.record_privacy_event(user_id, "ACCOUNT_DATA_DELETED", {"tables": sorted(removed)})

    assert removed["transactions"] == 3
    assert removed["source_observations"] == 3
    assert db.list_transactions(user_id, None) == []
    assert db.list_coverage(user_id) == []
    assert db.list_imports(user_id) == []
    assert ledger.read_aggregate(user_id)["total_spending"] == 0
    assert privacy_database_status(user_id)["retained"]["canonical_transactions"] == 0


def test_deleting_one_account_does_not_touch_another():
    keeper, leaver = _user(), _user()
    _seed(keeper, 2)
    _seed(leaver, 4)

    db.purge_user(leaver)

    assert ledger.read_aggregate(leaver)["total_spending"] == 0
    assert ledger.read_aggregate(keeper)["total_spending"] == 200
    assert len(db.list_transactions(keeper, None)) == 2
