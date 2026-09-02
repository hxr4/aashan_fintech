from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable

from app.models.transaction import Transaction


def _round(value: float) -> float:
    return round(float(value), 2)


def aggregate_transactions(transactions: Iterable[Transaction]) -> Dict[str, Any]:
    items = list(transactions)
    categories = defaultdict(float)
    budget_categories = defaultdict(float)
    monthly = defaultdict(float)
    daily = defaultdict(float)
    weekend = 0.0
    weekday = 0.0
    total_debit = 0.0
    total_credit = 0.0
    for transaction in items:
        if transaction.transaction_type == "TRANSFER" or transaction.is_transfer:
            continue
        if transaction.transaction_type == "CREDIT":
            total_credit += transaction.amount
            continue
        total_debit += transaction.amount
        category = transaction.category or "Other"
        categories[category] += transaction.amount
        if transaction.budget_status != "EXCLUDED":
            budget_categories[category] += transaction.amount
        monthly[transaction.date.strftime("%Y-%m")] += transaction.amount
        daily[transaction.date.strftime("%Y-%m-%d")] += transaction.amount
        if transaction.date.weekday() >= 5:
            weekend += transaction.amount
        else:
            weekday += transaction.amount
    total_spending = total_debit
    day_count = len(daily)
    return {
        "total_debit": _round(total_debit),
        "total_credit": _round(total_credit),
        "total_spending": _round(total_spending),
        "net_cash_flow": _round(total_credit - total_debit),
        "categories": {key: _round(value) for key, value in sorted(categories.items())},
        "budget_categories": {key: _round(value) for key, value in sorted(budget_categories.items())},
        "monthly": {key: _round(value) for key, value in sorted(monthly.items())},
        "daily": {key: _round(value) for key, value in sorted(daily.items())},
        "average_daily_spending": _round(total_spending / day_count if day_count else 0),
        "category_percentages": {
            key: _round((value / total_spending) * 100 if total_spending else 0)
            for key, value in sorted(categories.items())
        },
        "transaction_count": len(items),
        "weekend_vs_weekday": {"weekend": _round(weekend), "weekday": _round(weekday)},
    }
