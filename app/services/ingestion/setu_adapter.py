from typing import Any, Iterable

from app.models.ingestion import NormalizedTransactionInput
from app.services.normalizer import normalize_transaction
from app.services.setu_mapper import flatten_setu_transactions
from .base import FinancialSourceAdapter


class SetuAdapter(FinancialSourceAdapter):
    source_type = "SETU"

    def validate(self, source_input: Any) -> None:
        if not isinstance(source_input, (dict, list)):
            raise ValueError("INVALID_INPUT: Setu FI data must be a JSON object")

    def extract(self, source_input: Any) -> Iterable[NormalizedTransactionInput]:
        self.validate(source_input)
        rows = flatten_setu_transactions(source_input)
        for index, raw in enumerate(rows, start=1):
            try:
                transaction = normalize_transaction(raw)
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"NORMALIZATION_ERROR: Setu transaction {index} is invalid") from exc
            direction = transaction.transaction_type if transaction.transaction_type in {"CREDIT", "DEBIT", "TRANSFER"} else "DEBIT"
            external_id = raw.get("external_id") or raw.get("transaction_id")
            yield NormalizedTransactionInput(
                transaction_at=transaction.date,
                value_date=transaction.date,
                amount=transaction.amount,
                direction=direction,
                transaction_type=direction,
                description=transaction.description,
                mode=transaction.mode,
                source_type="SETU",
                source_record_id=str(raw.get("source_record_id") or index),
                external_id=str(external_id) if external_id else None,
            )
