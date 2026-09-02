import csv
import io
from typing import Any, Iterable, Optional

from app.models.ingestion import NormalizedTransactionInput
from app.services.normalizer import normalize_transaction
from .base import FinancialSourceAdapter


class CSVAdapter(FinancialSourceAdapter):
    source_type = "CSV"

    def validate(self, source_input: Any) -> None:
        if not isinstance(source_input, (bytes, bytearray, str)):
            raise ValueError("INVALID_INPUT: CSV input must be bytes or text")
        if not source_input:
            raise ValueError("INVALID_FILE: CSV contains no data")

    def _rows(self, source_input: Any) -> list[dict[str, Any]]:
        self.validate(source_input)
        text = source_input.decode("utf-8-sig") if isinstance(source_input, (bytes, bytearray)) else str(source_input)
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows:
            raise ValueError("INVALID_FILE: CSV contains no data rows")
        if not rows[0]:
            raise ValueError("INVALID_FILE: CSV contains no header")
        return rows

    def extract(self, source_input: Any) -> Iterable[NormalizedTransactionInput]:
        for index, raw in enumerate(self._rows(source_input), start=1):
            try:
                transaction = normalize_transaction(raw)
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(f"NORMALIZATION_ERROR: row {index} is invalid") from exc
            direction = transaction.transaction_type if transaction.transaction_type in {"CREDIT", "DEBIT", "TRANSFER"} else "DEBIT"
            external_id = next(
                (
                    str(raw[key]).strip()
                    for key in ("external_id", "transaction_id", "transactionId", "reference", "reference_id", "id")
                    if raw.get(key) not in (None, "")
                ),
                None,
            )
            yield NormalizedTransactionInput(
                transaction_at=transaction.date,
                value_date=transaction.date,
                amount=transaction.amount,
                direction=direction,
                transaction_type=direction,
                description=transaction.description,
                mode=transaction.mode,
                source_type="CSV",
                source_record_id=str(index),
                external_id=external_id,
            )
