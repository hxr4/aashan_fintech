from typing import Any, Dict, List

from app.services.money import as_float, to_decimal


def budget_status(categories: Dict[str, float], budgets: Dict[str, float]) -> List[Dict[str, Any]]:
    result = []
    for category, budget in sorted(budgets.items()):
        budget_value = to_decimal(budget)
        spent = to_decimal(categories.get(category, 0))
        result.append({
            "category": category,
            "budget": as_float(budget_value),
            "spent": as_float(spent),
            "percentage_used": as_float((spent / budget_value) * 100) if budget_value else 0,
            "remaining": as_float(budget_value - spent),
            "over_budget": spent > budget_value,
        })
    return result

