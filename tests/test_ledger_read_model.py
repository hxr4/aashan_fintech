"""The defect this suite exists to prevent: a second import replacing the first."""

import uuid
from datetime import datetime, timezone

from app.database import db
from app.models.ingestion import NormalizedTransactionInput, TransactionReviewRequest
from app.services import ledger
from app.services.ingestion import CSVAdapter
from app.services.ingestion.service import ingest_with_adapter
from app.services.review import review_transaction


def _user() -> str:
    return "ledger-" + uuid.uuid4().hex


def test_two_imports_accumulate_instead_of_replacing():
    user_id = _user()
    ingest_with_adapter(
        CSVAdapter(),
        b"date,description,amount,mode,type\n2026-07-01,SWIGGY ORDER,500,UPI,DEBIT\n",
        user_id,
        idempotency_key="july",
    )
    assert ledger.read_aggregate(user_id)["total_spending"] == 500

    second = ingest_with_adapter(
        CSVAdapter(),
        b"date,description,amount,mode,type\n2026-08-01,UBER RIDE,300,UPI,DEBIT\n",
        user_id,
        idempotency_key="august",
    )

    # Before the ledger became the read model this returned 300: the newest
    # snapshot covered only the second import and silently replaced the first.
    assert second["aggregate"]["total_spending"] == 800
    assert ledger.read_aggregate(user_id)["total_spending"] == 800
    assert ledger.read_aggregate(user_id)["monthly"] == {"2026-07": 500.0, "2026-08": 300.0}


def test_ledger_totals_survive_a_third_import():
    user_id = _user()
    for month, amount in (("07", 500), ("08", 300), ("09", 250)):
        ingest_with_adapter(
            CSVAdapter(),
            f"date,description,amount,mode,type\n2026-{month}-05,SHOP,{amount},UPI,DEBIT\n".encode(),
            user_id,
            idempotency_key=month,
        )
    assert ledger.read_aggregate(user_id)["total_spending"] == 1050
    assert len(ledger.read_aggregate(user_id)["monthly"]) == 3


def test_user_category_correction_is_not_overwritten_by_the_classifier():
    user_id = _user()
    ingest_with_adapter(
        CSVAdapter(),
        b"date,description,amount,mode,type\n2026-08-01,SWIGGY ORDER,500,UPI,DEBIT\n",
        user_id,
        idempotency_key="one",
    )
    transaction = db.list_transactions(user_id, "CONFIRMED")[0]
    assert transaction["category_name"] == "Food"

    review_transaction(
        user_id,
        transaction["id"],
        TransactionReviewRequest(action="CORRECT_CATEGORY", category="Education"),
    )

    # Re-aggregating must read the stored category, not re-run the classifier,
    # which would put this straight back to Food.
    aggregate = ledger.read_aggregate(user_id)
    assert aggregate["categories"] == {"Education": 500.0}


def test_aggregate_excludes_rows_that_are_not_confirmed():
    user_id = _user()
    import_record = db.create_import(user_id, "MANUAL")
    item = NormalizedTransactionInput(
        transaction_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        amount=100,
        direction="DEBIT",
        transaction_type="DEBIT",
        description="PENDING THING",
        mode="UPI",
        source_type="MANUAL",
    )
    candidate_id = db.create_candidate(
        user_id, import_record["id"], item, "Food", "fallback", 0.0,
        classification_status="AMBIGUOUS", review_status="PENDING_REVIEW",
        transaction_status="PENDING_REVIEW", budget_status="UNDECIDED",
    )
    assert ledger.read_aggregate(user_id)["total_spending"] == 0
    assert candidate_id
