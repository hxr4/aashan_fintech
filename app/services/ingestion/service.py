from typing import Any, Dict, Optional

from app.database import db
from app.models.ingestion import NormalizedTransactionInput
from app.models.transaction import Transaction
import app.services.pipeline as pipeline
from app.services.merchant_rules import apply_user_merchant_rules
from app.services import ledger
from .base import FinancialSourceAdapter


class IngestionResult(Dict[str, Any]):
    pass


def _safe_error(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    return message[:240] or "Processing failed"


def _classify_for_user(transaction: Transaction, user_id: str) -> Dict[str, Any]:
    classified = pipeline.Categorizer().classify(transaction)
    transaction.category = classified.get("category")
    transaction.classification_method = classified.get("classification_method")
    transaction.confidence = classified.get("confidence")
    apply_user_merchant_rules([transaction], user_id)
    return {
        "category": transaction.category,
        "classification_method": transaction.classification_method,
        "confidence": transaction.confidence,
    }


def ingest_with_adapter(
    adapter: FinancialSourceAdapter,
    source_input: Any,
    user_id: str,
    *,
    filename: Optional[str] = None,
    account_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    budgets: Optional[Dict[str, float]] = None,
) -> IngestionResult:
    """Run one source through the shared import/candidate/transaction boundary."""
    source = adapter.source_type
    import_record = db.create_import(user_id, source, filename, account_id, idempotency_key)
    if import_record.get("existing"):
        return IngestionResult({
            "status": "already_processed",
            "import_id": import_record["id"],
            "job_id": None,
            "rows_received": import_record.get("row_count", 0),
            "rows_confirmed": 0,
            "duplicates": 0,
            "candidates_pending_review": 0,
            "reconciled": 0,
            "rows_processed": import_record.get("row_count", 0),
            "aggregate": ledger.read_aggregate(user_id),
        })

    import_id = import_record["id"]
    job_id = db.create_processing_job(user_id, import_id, f"{source}_INGESTION")
    counts = {"rows_received": 0, "rows_confirmed": 0, "duplicates": 0, "reconciled": 0, "candidates_pending_review": 0}
    try:
        db.update_processing_checkpoint(job_id, user_id, "SOURCE_VALIDATED", progress={"source": source})
        normalized = list(adapter.extract(source_input))
        counts["rows_received"] = len(normalized)
        db.update_processing_checkpoint(job_id, user_id, "NORMALIZATION_COMPLETED", progress={"rows": len(normalized)})
        db.update_processing_checkpoint(job_id, user_id, "CLASSIFICATION_STARTED")

        categorized_rows: list[Dict[str, Any]] = []
        for item in normalized:
            transaction = Transaction(
                date=item.transaction_at,
                transaction_at=item.transaction_at,
                value_date=item.value_date,
                description=item.description,
                amount=item.amount,
                mode=item.mode,
                transaction_type=item.direction,
                source_type=item.source_type,
                source=item.source_type,
                source_record_id=item.source_record_id,
                external_id=item.external_id,
                account_id=item.account_id,
                currency=item.currency,
                merchant_candidate=item.merchant_candidate,
            )
            classification = _classify_for_user(transaction, user_id)
            category = classification["category"]
            classification_method = classification["classification_method"]
            confidence = classification["confidence"]
            # Two different kinds of uncertainty, deliberately not conflated.
            # Not knowing the *category* is not a reason to withhold the amount
            # from the user's totals -- the money definitely left the account.
            # Only uncertainty about the transaction itself does that.
            classification_status = "AMBIGUOUS" if classification_method == "fallback" else "AUTO_CLASSIFIED"
            needs_category = classification_status == "AMBIGUOUS"
            is_transfer = item.direction == "TRANSFER"
            budget_status = "EXCLUDED" if is_transfer else "INCLUDED"
            transfer_status = "CONFIRMED" if is_transfer else "NOT_TRANSFER"
            candidate_id = db.create_candidate(
                user_id,
                import_id,
                item,
                category,
                classification_method,
                confidence,
                classification_status=classification_status,
                review_status="PENDING_REVIEW" if needs_category else "CONFIRMED",
                transaction_status="CONFIRMED",
                budget_status=budget_status,
                transfer_status=transfer_status,
            )
            created = db.create_transaction(
                user_id,
                import_id,
                candidate_id,
                item,
                category,
                classification_method,
                confidence,
                classification_status=classification_status,
                transaction_status="CONFIRMED",
                budget_status=budget_status,
                transfer_status=transfer_status,
            )
            if created.get("duplicate"):
                # A cross-source match is a second witness to a transaction we
                # already hold, not a duplicate the user needs to worry about.
                if created.get("cross_source"):
                    counts["reconciled"] += 1
                else:
                    counts["duplicates"] += 1
                db.update_candidate(user_id, candidate_id, "DUPLICATE", "DUPLICATE", classification_status)
                continue
            if created.get("possible_duplicate"):
                # Held out of the totals until a human decides.
                counts["candidates_pending_review"] += 1
                db.update_candidate(user_id, candidate_id, "PENDING_REVIEW", "PENDING_REVIEW", classification_status)
                continue
            counts["rows_confirmed"] += 1
            if needs_category:
                counts["candidates_pending_review"] += 1
            categorized_rows.append({
                "date": item.transaction_at.isoformat(),
                "description": item.description,
                "amount": item.amount,
                "mode": item.mode,
                "transaction_type": item.direction,
                "budget_status": budget_status,
            })

        db.update_processing_checkpoint(job_id, user_id, "CLASSIFICATION_COMPLETED", progress=counts)
        db.update_processing_checkpoint(job_id, user_id, "PERSISTENCE_COMPLETED", progress={"confirmed": counts["rows_confirmed"]})
        # The ledger is the read model: recompute from every confirmed row the
        # owner has, not from the rows of this import alone.
        aggregate = ledger.compute_aggregate(
            user_id, budgets, source=f"INGEST_{source}", import_id=import_id
        )
        db.update_processing_checkpoint(job_id, user_id, "AGGREGATION_COMPLETED", progress={"confirmed": counts["rows_confirmed"]})
        final_status = "PARTIAL" if counts["duplicates"] else "COMPLETED"
        db.complete_import(import_id, user_id, final_status, counts["rows_received"])
        db.complete_processing_job(job_id, user_id, "COMPLETED")
        return IngestionResult({
            "status": "processed" if final_status == "COMPLETED" else "partial",
            "import_id": import_id,
            "job_id": job_id,
            **counts,
            "rows_processed": counts["rows_received"],
            "aggregate": aggregate,
        })
    except (ValueError, TypeError, KeyError) as exc:
        message = _safe_error(exc)
        db.complete_import(import_id, user_id, "FAILED", counts["rows_received"], "INVALID_INPUT", message)
        db.complete_processing_job(job_id, user_id, "FAILED", "INVALID_INPUT", message)
        raise
    except Exception as exc:
        message = _safe_error(exc)
        db.complete_import(import_id, user_id, "FAILED", counts["rows_received"], "PROCESSING_FAILED", message)
        db.complete_processing_job(job_id, user_id, "FAILED", "PROCESSING_FAILED", message)
        raise
