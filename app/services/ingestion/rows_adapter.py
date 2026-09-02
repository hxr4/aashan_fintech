"""Adapter for sources that already produce normalizer-shaped rows.

SMS parsing, the mock Account Aggregator provider and the demo generator all
used to call the processing kernel directly, which meant they never created
canonical transactions and never appeared in the ledger. They now enter through
the same adapter boundary as CSV.
"""

from typing import Any, Dict, Iterable, List

from app.models.ingestion import NormalizedTransactionInput, SourceType
from app.services.normalizer import normalize_transaction
from .base import FinancialSourceAdapter


class RowsAdapter(FinancialSourceAdapter):
    def __init__(self, source_type: SourceType = "MANUAL") -> None:
        self.source_type = source_type

    def validate(self, source_input: Any) -> None:
        if not isinstance(source_input, (list, tuple)):
            raise ValueError("INVALID_INPUT: rows must be a list")
        if not source_input:
            raise ValueError("INVALID_FILE: no rows supplied")

    def extract(self, source_input: Any) -> Iterable[NormalizedTransactionInput]:
        self.validate(source_input)
        rows: List[Dict[str, Any]] = [row for row in source_input if isinstance(row, dict)]
        if not rows:
            raise ValueError("INVALID_FILE: no usable rows supplied")
        for index, raw in enumerate(rows, start=1):
            try:
                transaction = normalize_transaction(raw)
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"NORMALIZATION_ERROR: row {index} is invalid") from exc
            direction = (
                transaction.transaction_type
                if transaction.transaction_type in {"CREDIT", "DEBIT", "TRANSFER"}
                else "DEBIT"
            )
            external_id = raw.get("external_id") or raw.get("transaction_id")
            yield NormalizedTransactionInput(
                transaction_at=transaction.date,
                value_date=transaction.date,
                amount=transaction.amount,
                direction=direction,
                transaction_type=direction,
                description=transaction.description,
                mode=transaction.mode,
                source_type=self.source_type,
                source_record_id=str(index),
                external_id=str(external_id) if external_id else None,
            )
