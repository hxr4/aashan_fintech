from datetime import datetime
from typing import Any, Dict, Optional

from app.database import db
from app.models.ingestion import NormalizedTransactionInput, TransactionReviewRequest
from app.services.pipeline import process_raw_rows


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _candidate_item(row: Dict[str, Any], request: TransactionReviewRequest) -> NormalizedTransactionInput:
    direction = "TRANSFER" if request.action == "MARK_TRANSFER" else row.get("direction", "DEBIT")
    description = request.description if request.description is not None else row.get("description") or ""
    return NormalizedTransactionInput(
        transaction_at=_as_datetime(row["transaction_at"]),
        value_date=_as_datetime(row["value_date"]) if row.get("value_date") else None,
        amount=request.amount if request.amount is not None else float(row["amount"]),
        currency=row.get("currency") or "INR",
        direction=direction if direction in {"CREDIT", "DEBIT", "TRANSFER"} else "DEBIT",
        transaction_type=direction if direction in {"CREDIT", "DEBIT", "TRANSFER"} else "DEBIT",
        description=description,
        mode=row.get("mode") or "UNKNOWN",
        merchant_candidate=request.merchant if request.merchant is not None else row.get("merchant_candidate"),
        merchant_confidence=1.0 if request.merchant is not None else row.get("merchant_confidence"),
        category_candidate=request.category if request.category is not None else row.get("category_candidate"),
        source_type=row.get("source") or "MANUAL",
        source_record_id=row.get("source_record_id"),
        external_id=row.get("external_id"),
        account_id=row.get("account_id"),
    )


def _reaggregate_confirmed(user_id: str) -> Dict[str, Any]:
    rows = []
    for row in db.list_transactions(user_id, "CONFIRMED"):
        rows.append({
            "date": row["transaction_at"],
            "description": row.get("description") or "",
            "amount": row["amount"],
            "mode": row.get("mode") or "UNKNOWN",
            "transaction_type": row.get("transaction_type") or row.get("direction") or "DEBIT",
            "budget_status": row.get("budget_status") or row.get("budget_inclusion") or "UNDECIDED",
        })
    return process_raw_rows(rows, db.get_budgets(user_id), user_id=user_id, source="REVIEW")


def review_candidate(user_id: str, candidate_id: str, request: TransactionReviewRequest) -> Optional[Dict[str, Any]]:
    row = db.get_candidate(user_id, candidate_id)
    if not row:
        return None
    changes = request.model_dump(exclude_none=True)
    if request.action in {"REJECT", "MARK_DUPLICATE"}:
        transaction_status = "DUPLICATE" if request.action == "MARK_DUPLICATE" else "REJECTED"
        db.update_candidate(user_id, candidate_id, transaction_status, transaction_status, "USER_CONFIRMED")
        review_id = db.create_review(user_id, candidate_id, None, request.action, changes)
        return {"candidate_id": candidate_id, "review_id": review_id, "status": transaction_status}

    item = _candidate_item(row, request)
    category = request.category or row.get("category_candidate")
    transfer_status = "CONFIRMED" if request.action == "MARK_TRANSFER" else row.get("transfer_status") or "NOT_TRANSFER"
    budget_status = "EXCLUDED" if request.action in {"EXCLUDE_FROM_BUDGET", "MARK_TRANSFER"} else "INCLUDED"
    classification_status = "USER_CORRECTED" if request.action in {"EDIT", "CORRECT_CATEGORY", "CORRECT_MERCHANT"} else "USER_CONFIRMED"
    created = db.create_transaction(
        user_id,
        row["import_id"],
        candidate_id,
        item,
        category,
        "user_review",
        1.0,
        classification_status=classification_status,
        transaction_status="CONFIRMED",
        budget_status=budget_status,
        transfer_status=transfer_status,
    )
    if created.get("duplicate"):
        db.update_candidate(user_id, candidate_id, "DUPLICATE", "DUPLICATE", "USER_CONFIRMED")
        status = "DUPLICATE"
    else:
        db.update_candidate(user_id, candidate_id, "CONFIRMED", "CONFIRMED", classification_status)
        status = "CONFIRMED"
    review_id = db.create_review(user_id, candidate_id, created.get("id"), request.action, changes)
    if request.action in {"CORRECT_CATEGORY", "CORRECT_MERCHANT"} and item.merchant_candidate:
        db.create_merchant_rule(user_id, item.merchant_candidate, category)
    aggregate = _reaggregate_confirmed(user_id) if status == "CONFIRMED" else db.latest_aggregate(user_id)
    return {"candidate_id": candidate_id, "transaction_id": created.get("id"), "review_id": review_id, "status": status, "aggregate": aggregate}


def review_transaction(user_id: str, transaction_id: str, request: TransactionReviewRequest) -> Optional[Dict[str, Any]]:
    row = db.get_transaction(user_id, transaction_id)
    if not row:
        return None
    changes = request.model_dump(exclude_none=True)
    updates: Dict[str, Any] = {"classification_status": "USER_CORRECTED"}
    if request.category is not None:
        updates["category_name"] = request.category
    if request.merchant is not None:
        updates["merchant_candidate"] = request.merchant
    if request.action == "INCLUDE_IN_BUDGET":
        updates.update({"budget_status": "INCLUDED", "budget_inclusion": "INCLUDED"})
    elif request.action in {"EXCLUDE_FROM_BUDGET", "MARK_TRANSFER"}:
        updates.update({"budget_status": "EXCLUDED", "budget_inclusion": "EXCLUDED"})
    if request.action == "MARK_TRANSFER":
        updates.update({"transaction_type": "TRANSFER", "transfer_status": "CONFIRMED", "is_transfer": True})
    if request.action == "MARK_DUPLICATE":
        updates.update({"transaction_status": "DUPLICATE", "status": "DUPLICATE", "duplicate_status": "CONFIRMED_DUPLICATE", "budget_status": "EXCLUDED", "budget_inclusion": "EXCLUDED"})
    if request.action == "REJECT":
        updates.update({"transaction_status": "REJECTED", "status": "REJECTED", "budget_status": "EXCLUDED", "budget_inclusion": "EXCLUDED"})
    if request.action == "APPROVE":
        updates["classification_status"] = "USER_CONFIRMED"
    db.update_transaction(user_id, transaction_id, updates)
    review_id = db.create_review(user_id, None, transaction_id, request.action, changes)
    if request.action in {"CORRECT_CATEGORY", "CORRECT_MERCHANT"} and (request.merchant or row.get("merchant_candidate")):
        db.create_merchant_rule(user_id, request.merchant or row["merchant_candidate"], request.category)
    return {"transaction_id": transaction_id, "review_id": review_id, "status": updates.get("transaction_status", row.get("transaction_status", "CONFIRMED")), "aggregate": _reaggregate_confirmed(user_id)}
