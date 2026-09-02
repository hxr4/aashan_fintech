from typing import Any, Dict, List


def budget_status(categories: Dict[str, float], budgets: Dict[str, float]) -> List[Dict[str, Any]]:
    result = []
    for category, budget in sorted(budgets.items()):
        budget_value = float(budget)
        spent = float(categories.get(category, 0))
        result.append({
            "category": category,
            "budget": round(budget_value, 2),
            "spent": round(spent, 2),
            "percentage_used": round((spent / budget_value) * 100 if budget_value else 0, 2),
            "remaining": round(budget_value - spent, 2),
            "over_budget": spent > budget_value,
        })
    return result

