import re
from typing import Iterable

from app.database.db import list_merchant_rules
from app.models.transaction import Transaction


def apply_user_merchant_rules(transactions: Iterable[Transaction], user_id: str) -> list[Transaction]:
    """Apply owner-scoped merchant rules after the shared classifier runs."""
    items = list(transactions)
    rules = list_merchant_rules(user_id)
    if not rules:
        return items
    for transaction in items:
        text = " ".join(filter(None, [transaction.merchant, transaction.description])).lower()
        for rule in rules:
            pattern = str(rule.get("merchant_pattern") or "").strip().lower()
            category = rule.get("category_name")
            if pattern and category and re.search(re.escape(pattern), text):
                transaction.category = category
                transaction.classification_method = "user_rule"
                transaction.confidence = 1.0
                break
    return items
