"""One purchase seen by several sources must remain one transaction."""

import uuid
from datetime import datetime, timedelta, timezone

from app.database import db
from app.models.ingestion import NormalizedTransactionInput
from app.services import ledger
from app.services.ingestion import CSVAdapter, RowsAdapter
from app.services.ingestion.service import ingest_with_adapter


def _user() -> str:
    return "recon-" + uuid.uuid4().hex


def _row(day: str, description: str, amount: float, direction: str = "DEBIT"):
    return {"date": day, "description": description, "amount": amount, "mode": "UPI", "transaction_type": direction}


def test_the_same_csv_twice_is_one_transaction_with_two_observations():
    user_id = _user()
    content = b"date,description,amount,mode,type\n2026-08-18,DOMAIN PURCHASE,348,UPI,DEBIT\n"
    first = ingest_with_adapter(CSVAdapter(), content, user_id, idempotency_key="a")
    second = ingest_with_adapter(CSVAdapter(), content, user_id, idempotency_key="b")

    assert first["rows_confirmed"] == 1
    assert second["rows_confirmed"] == 0
    assert second["duplicates"] == 1

    rows = db.list_transactions(user_id, "CONFIRMED")
    assert len(rows) == 1
    assert ledger.read_aggregate(user_id)["total_spending"] == 348
    assert len(db.list_observations(user_id, rows[0]["id"])) == 2


def test_sms_then_statement_reconcile_into_one_transaction():
    """The slide-2 case: phone says Rs348, bank says Rs348, answer is Rs348."""
    user_id = _user()
    ingest_with_adapter(RowsAdapter("SMS"), [_row("2026-08-18", "Rs 348 debited UPI DOMAIN", 348)], user_id)
    assert ledger.read_aggregate(user_id)["total_spending"] == 348

    statement = ingest_with_adapter(
        CSVAdapter(),
        b"date,description,amount,mode,type\n2026-08-20,UPI-DOMAIN-PURCHASE-99887766,348,UPI,DEBIT\n",
        user_id,
        idempotency_key="stmt",
    )

    assert statement["reconciled"] == 1
    assert statement["rows_confirmed"] == 0
    rows = db.list_transactions(user_id, "CONFIRMED")
    assert len(rows) == 1
    assert ledger.read_aggregate(user_id)["total_spending"] == 348

    observations = db.list_observations(user_id, rows[0]["id"])
    assert {observation["source"] for observation in observations} == {"SMS", "CSV"}
    assert {observation["match_method"] for observation in observations} == {"NEW", "CROSS_SOURCE_WINDOW"}


def test_two_identical_amounts_from_one_source_stay_two_purchases():
    """Rs100 of chai on Monday and Rs100 on Tuesday is not a duplicate."""
    user_id = _user()
    ingest_with_adapter(
        RowsAdapter("SMS"),
        [_row("2026-08-10", "CHAI STALL", 100), _row("2026-08-11", "CHAI STALL", 100)],
        user_id,
    )
    assert len(db.list_transactions(user_id, "CONFIRMED")) == 2
    assert ledger.read_aggregate(user_id)["total_spending"] == 200


def test_a_different_amount_is_never_merged():
    user_id = _user()
    ingest_with_adapter(RowsAdapter("SMS"), [_row("2026-08-18", "FUEL", 974.71)], user_id)
    ingest_with_adapter(
        CSVAdapter(),
        b"date,description,amount,mode,type\n2026-08-19,FUEL STATION,1000,CARD,DEBIT\n",
        user_id,
        idempotency_key="fuel",
    )
    # Amount differs, so this is an authorisation-vs-settlement question for a
    # human, not something to silently merge.
    assert len(db.list_transactions(user_id, "CONFIRMED")) == 2


def test_outside_the_window_is_not_merged():
    user_id = _user()
    ingest_with_adapter(RowsAdapter("SMS"), [_row("2026-08-01", "SHOP", 500)], user_id)
    ingest_with_adapter(
        CSVAdapter(),
        b"date,description,amount,mode,type\n2026-08-20,SHOP,500,UPI,DEBIT\n",
        user_id,
        idempotency_key="far",
    )
    assert len(db.list_transactions(user_id, "CONFIRMED")) == 2


def test_external_id_matches_across_sources_not_within_one():
    user_id = _user()
    import_record = db.create_import(user_id, "SMS")
    base = dict(
        transaction_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        amount=250.0, currency="INR", direction="DEBIT", transaction_type="DEBIT",
        description="ONAM FUND", mode="UPI", external_id="BANKREF-42",
    )
    first = db.create_transaction(
        user_id, import_record["id"], None,
        NormalizedTransactionInput(source_type="SMS", **base), "Other", "fallback", 0.0,
    )
    # Same bank reference arriving later through a statement is the same event.
    second = db.create_transaction(
        user_id, import_record["id"], None,
        NormalizedTransactionInput(source_type="CSV", **base), "Other", "fallback", 0.0,
    )
    assert first["created"] is True
    assert second["created"] is False
    assert second["match_method"] == "EXTERNAL_ID"
    assert len(db.list_transactions(user_id, "CONFIRMED")) == 1
