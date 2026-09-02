from abc import ABC, abstractmethod
from typing import Any, Iterable

from app.models.ingestion import NormalizedTransactionInput, SourceType


class FinancialSourceAdapter(ABC):
    """Source boundary; adapters never own aggregation, budgets, or auth."""

    source_type: SourceType

    @abstractmethod
    def validate(self, source_input: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def extract(self, source_input: Any) -> Iterable[NormalizedTransactionInput]:
        raise NotImplementedError
