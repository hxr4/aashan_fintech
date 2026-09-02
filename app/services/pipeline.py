from typing import Any, Dict, Iterable, List, Optional

from app.database.db import save_aggregate
from app.services.aggregator import aggregate_transactions
from app.services.anomaly import detect_anomalies
from app.services.budget import budget_status
from app.services.categorizer import Categorizer
from app.services.normalizer import normalize_transactions
from app.services.privacy import forget_raw_transactions
from app.services.merchant_rules import apply_user_merchant_rules


def process_raw_rows(
    rows: Iterable[Dict[str, Any]],
    budgets: Optional[Dict[str, float]] = None,
    *,
    user_id: Optional[str] = None,
    source: str = "PIPELINE",
    import_id: Optional[str] = None,
) -> Dict[str, Any]:
    raw = list(rows)
    transactions = normalize_transactions(raw)
    # The categorizer operates on normalized objects before the privacy boundary.
    categorized = Categorizer().categorize_transactions(transactions)
    if user_id:
        categorized = apply_user_merchant_rules(categorized, user_id)
    aggregate = aggregate_transactions(categorized)
    aggregate["anomalies"] = detect_anomalies(categorized)
    aggregate["budget_status"] = budget_status(aggregate.get("budget_categories", aggregate["categories"]), budgets or {})
    # Keep classification metadata useful to the caller without returning raw
    # descriptions or narrations, and persist no raw transaction objects.
    aggregate["classification_metadata"] = [
        {
            "category": transaction.category or "Other",
            "classification_method": transaction.classification_method or "fallback",
            "confidence": transaction.confidence if transaction.confidence is not None else 0.0,
            "transaction_type": transaction.transaction_type,
        }
        for transaction in categorized
    ]
    save_aggregate(aggregate, user_id=user_id or "00000000-0000-0000-0000-000000000001", source=source, import_id=import_id)
    forget_raw_transactions(raw)
    forget_raw_transactions(categorized)
    return aggregate
