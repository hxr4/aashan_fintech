from datetime import datetime

from app.models.transaction import Transaction
from app.services.aggregator import aggregate_transactions
from app.services.budget import budget_status


def test_aggregation_and_budget():
    transactions = [
        Transaction(date=datetime(2026, 8, 1), description="food", amount=100, category="Food"),
        Transaction(date=datetime(2026, 8, 2), description="salary", amount=1000, transaction_type="CREDIT", category="Salary"),
        Transaction(date=datetime(2026, 8, 8), description="shopping", amount=200, category="Shopping"),
    ]
    result = aggregate_transactions(transactions)
    assert result["total_spending"] == 300
    assert result["total_credit"] == 1000
    assert result["net_cash_flow"] == 700
    assert result["categories"] == {"Food": 100, "Shopping": 200}
    assert budget_status(result["categories"], {"Food": 150})[0]["remaining"] == 50
