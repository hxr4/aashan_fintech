"""The canonical transaction ledger is the read model for every financial number.

Before this module, dashboards read `aggregate_snapshots` -- a JSON document
written at ingestion time from the rows of that one import. Two imports
therefore produced two snapshots, and the newest one won, so a second import
silently replaced the first instead of adding to it.

Every financial figure now derives from the confirmed rows in `transactions`.
Stored classification is trusted as-is: the aggregate never re-runs the
classifier, because doing so would quietly discard a user's own correction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import db
from app.models.transaction import Transaction
from app.services.aggregator import aggregate_transactions
from app.services.anomaly import detect_anomalies
from app.services.budget import budget_status
from app.services import coverage as coverage_service


EMPTY_AGGREGATE: Dict[str, Any] = {
    "total_spending": 0,
    "total_debit": 0,
    "total_credit": 0,
    "net_cash_flow": 0,
    "categories": {},
    "budget_categories": {},
    "monthly": {},
    "daily": {},
    "average_daily_spending": 0,
    "category_percentages": {},
    "transaction_count": 0,
    "weekend_vs_weekday": {"weekend": 0, "weekday": 0},
    "anomalies": [],
    "budget_status": [],
    "classification_metadata": [],
    "coverage": {},
    "rates": {},
}


def empty_aggregate() -> Dict[str, Any]:
    """A fresh copy, so callers cannot mutate the shared default."""
    import copy

    return copy.deepcopy(EMPTY_AGGREGATE)


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")


def _row_to_transaction(row: Dict[str, Any]) -> Transaction:
    direction = row.get("transaction_type") or row.get("direction") or "DEBIT"
    confidence = row.get("classification_confidence")
    return Transaction(
        date=_as_datetime(row["transaction_at"]),
        transaction_at=_as_datetime(row["transaction_at"]),
        value_date=_as_datetime(row["value_date"]) if row.get("value_date") else None,
        description=row.get("description") or "",
        amount=float(row["amount"]),
        mode=row.get("mode") or "UNKNOWN",
        transaction_type=direction,
        category=row.get("category_name"),
        classification_method=row.get("classification_method"),
        confidence=float(confidence) if confidence is not None else None,
        currency=row.get("currency") or "INR",
        budget_status=row.get("budget_status") or row.get("budget_inclusion") or "UNDECIDED",
        transfer_status=row.get("transfer_status") or "NOT_TRANSFER",
        duplicate_status=row.get("duplicate_status") or "NOT_DUPLICATE",
        is_transfer=bool(row.get("is_transfer")),
        classification_status=row.get("classification_status") or "CLASSIFIED",
        transaction_status=row.get("transaction_status") or "CONFIRMED",
        source=row.get("source"),
        source_type=row.get("source"),
        account_id=row.get("account_id"),
        import_id=row.get("import_id"),
        external_id=row.get("external_id"),
        merchant_candidate=row.get("merchant_candidate"),
    )


def confirmed_transactions(user_id: str) -> List[Transaction]:
    """Every confirmed row the owner has, oldest first.

    Ascending order keeps `classification_metadata` in the order the user
    supplied the data, which is the order a statement or CSV reads in.
    """
    rows = db.list_transactions(user_id, "CONFIRMED")
    transactions = [_row_to_transaction(row) for row in rows]
    transactions.sort(key=lambda item: item.date)
    return transactions


def compute_aggregate(
    user_id: str,
    budgets: Optional[Dict[str, float]] = None,
    *,
    persist: bool = True,
    source: str = "LEDGER",
    import_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Recompute the owner's whole financial picture from the ledger."""
    transactions = confirmed_transactions(user_id)
    if not transactions:
        aggregate = empty_aggregate()
    else:
        aggregate = aggregate_transactions(transactions)
        aggregate["anomalies"] = detect_anomalies(transactions)
        aggregate["classification_metadata"] = [
            {
                "category": transaction.category or "Other",
                "classification_method": transaction.classification_method or "fallback",
                "confidence": transaction.confidence if transaction.confidence is not None else 0.0,
                "transaction_type": transaction.transaction_type,
            }
            for transaction in transactions
        ]
    windows = db.list_coverage(user_id)
    aggregate["coverage"] = coverage_service.summarize(
        windows, days_with_transactions=len(aggregate.get("daily", {}))
    )
    aggregate["rates"] = coverage_service.rates(
        aggregate.get("total_spending", 0), aggregate["coverage"]
    )
    configured = db.get_budgets(user_id) if budgets is None else budgets
    aggregate["budget_status"] = budget_status(
        aggregate.get("budget_categories", aggregate.get("categories", {})), configured
    )
    if persist:
        # Snapshots remain as an audit trail of what was shown and when.
        # Nothing reads them back as the source of truth any more.
        db.save_aggregate(aggregate, user_id=user_id, source=source, import_id=import_id)
    return aggregate


def read_aggregate(user_id: str) -> Dict[str, Any]:
    """What every dashboard endpoint reads. Never writes."""
    return compute_aggregate(user_id, persist=False)
