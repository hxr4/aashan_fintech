from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, Iterable

from app.models.transaction import Transaction
from app.services.money import ZERO, as_float, to_decimal


def aggregate_transactions(transactions: Iterable[Transaction]) -> Dict[str, Any]:
    """Sum in Decimal, present as float.

    Every running total below is a Decimal, so adding thousands of rows cannot
    drift the way repeated float addition does. Values are quantised once, on
    the way out, which is also the only place rounding happens.
    """
    items = list(transactions)
    categories: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    budget_categories: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    monthly: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    daily: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    weekend = ZERO
    weekday = ZERO
    total_debit = ZERO
    total_credit = ZERO

    for transaction in items:
        amount = to_decimal(transaction.amount)
        if transaction.transaction_type == "TRANSFER" or transaction.is_transfer:
            continue
        if transaction.transaction_type == "CREDIT":
            total_credit += amount
            continue
        total_debit += amount
        category = transaction.category or "Other"
        categories[category] += amount
        if transaction.budget_status != "EXCLUDED":
            budget_categories[category] += amount
        monthly[transaction.date.strftime("%Y-%m")] += amount
        daily[transaction.date.strftime("%Y-%m-%d")] += amount
        if transaction.date.weekday() >= 5:
            weekend += amount
        else:
            weekday += amount

    total_spending = total_debit
    day_count = len(daily)
    return {
        "total_debit": as_float(total_debit),
        "total_credit": as_float(total_credit),
        "total_spending": as_float(total_spending),
        "net_cash_flow": as_float(total_credit - total_debit),
        "categories": {key: as_float(value) for key, value in sorted(categories.items())},
        "budget_categories": {key: as_float(value) for key, value in sorted(budget_categories.items())},
        "monthly": {key: as_float(value) for key, value in sorted(monthly.items())},
        "daily": {key: as_float(value) for key, value in sorted(daily.items())},
        "average_daily_spending": as_float(total_spending / day_count) if day_count else 0,
        "category_percentages": {
            key: as_float(value / total_spending * 100) if total_spending else 0
            for key, value in sorted(categories.items())
        },
        "transaction_count": len(items),
        "weekend_vs_weekday": {"weekend": as_float(weekend), "weekday": as_float(weekday)},
    }
