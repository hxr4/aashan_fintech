from typing import Any, Dict


class InsightProvider:
    def answer(self, question: str, aggregates: Dict[str, Any]) -> str:
        raise NotImplementedError


class MockInsightProvider(InsightProvider):
    def answer(self, question: str, aggregates: Dict[str, Any]) -> str:
        normalized = question.lower()
        categories = aggregates.get("categories", {})
        budgets = aggregates.get("budget_status", [])
        anomalies = aggregates.get("anomalies", [])
        if not categories:
            return "There is not enough aggregate spending data yet. Run the demo or ingest data first."
        if "most" in normalized or "highest" in normalized:
            category, amount = max(categories.items(), key=lambda item: item[1])
            return "%s was your highest spending category at ₹%.2f." % (category, amount)
        for category in categories:
            if category.lower() in normalized:
                return "You spent ₹%.2f on %s." % (categories[category], category)
        if "compare" in normalized or "last month" in normalized:
            months = list(sorted(aggregates.get("monthly", {}).items()))
            if len(months) >= 2:
                current, previous = months[-1], months[-2]
                change = current[1] - previous[1]
                direction = "more" if change >= 0 else "less"
                return "You spent ₹%.2f %s this month than last month." % (abs(change), direction)
        exceeded = [item["category"] for item in budgets if item.get("over_budget")]
        if "budget" in normalized and exceeded:
            return "You exceeded the budget for %s." % ", ".join(exceeded)
        if "unusual" in normalized or "anomal" in normalized:
            return "%d unusual spending event(s) were detected." % len(anomalies)
        return "I can answer questions about your top category, category totals, monthly comparison, budgets, and anomalies."

