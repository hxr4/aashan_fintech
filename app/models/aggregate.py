from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AggregateSnapshot(BaseModel):
    total_debit: float = 0
    total_credit: float = 0
    total_spending: float = 0
    net_cash_flow: float = 0
    categories: Dict[str, float] = Field(default_factory=dict)
    budget_categories: Dict[str, float] = Field(default_factory=dict)
    monthly: Dict[str, float] = Field(default_factory=dict)
    daily: Dict[str, float] = Field(default_factory=dict)
    average_daily_spending: float = 0
    category_percentages: Dict[str, float] = Field(default_factory=dict)
    transaction_count: int = 0
    weekend_vs_weekday: Dict[str, float] = Field(default_factory=dict)
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    budget_status: List[Dict[str, Any]] = Field(default_factory=list)
    classification_metadata: List[Dict[str, Any]] = Field(default_factory=list)
