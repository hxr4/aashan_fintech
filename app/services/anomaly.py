from collections import defaultdict
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List

from app.models.transaction import Transaction


def detect_anomalies(transactions: Iterable[Transaction]) -> List[Dict[str, Any]]:
    grouped = defaultdict(list)
    for transaction in transactions:
        if transaction.transaction_type == "DEBIT":
            grouped[transaction.category or "Other"].append(transaction.amount)
    anomalies = []
    for category, values in grouped.items():
        if len(values) < 3:
            continue
        average = mean(values)
        deviation = pstdev(values)
        threshold = average + (1.5 * deviation if deviation else max(average * 0.75, 1))
        for amount in sorted(set(values)):
            if amount > threshold:
                anomalies.append({
                    "category": category,
                    "amount": round(amount, 2),
                    "is_anomaly": True,
                    "reason": "Amount is significantly above the normal spending range.",
                })
    return anomalies
