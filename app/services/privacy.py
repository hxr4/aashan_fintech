from typing import Any, List


def forget_raw_transactions(transactions: List[Any]) -> int:
    """Clear the in-memory raw object references after aggregation.

    This service intentionally does not serialize or persist the supplied objects.
    """
    count = len(transactions)
    transactions.clear()
    return count

