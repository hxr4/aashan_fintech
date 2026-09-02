import re
from datetime import datetime
from typing import Any, Dict, Iterable, List

from app.models.transaction import Transaction
from app.services.clock import to_ist


ALIASES = {
    "date": ["date", "Date", "transaction_date", "value_date", "transactionTimestamp"],
    "description": ["description", "Description", "narration", "details", "merchant"],
    "amount": ["amount", "Amount", "value", "transaction_amount"],
    "mode": ["mode", "Mode", "payment_mode", "channel"],
    "transaction_type": [
        "transaction_type", "Type", "type", "direction", "Direction",
        "credit_debit", "Credit/Debit", "debit_credit",
    ],
    "budget_status": ["budget_status", "budget_inclusion", "Budget Status"],
}

_CREDIT_INDICATORS = {"CREDIT", "CR", "CREDITED", "DEPOSIT", "DEPOSITED", "RECEIVED"}
_DEBIT_INDICATORS = {"DEBIT", "DR", "DEBITED", "WITHDRAWAL", "WITHDRAW", "PAID"}
_TRANSFER_INDICATORS = {"TRANSFER", "XFER", "INTERNALTRANSFER"}


def _normalize_key(value: Any) -> str:
    """Normalize exported CSV header spelling without changing its meaning."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _value(raw: Dict[str, Any], field: str, default: Any = None) -> Any:
    aliases = {_normalize_key(alias) for alias in ALIASES[field]}
    for raw_key, raw_value in raw.items():
        if _normalize_key(raw_key) in aliases and raw_value not in (None, ""):
            return raw_value
    return default


def _parse_date(value: Any) -> datetime:
    """Parse a source date and anchor it to Asia/Kolkata.

    A statement or an SMS carries local wall-clock time, so a naive value is
    treated as already-Indian rather than as UTC.
    """
    if isinstance(value, datetime):
        return to_ist(value)
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return to_ist(datetime.strptime(text[:19], fmt))
        except ValueError:
            pass
    return to_ist(text)


def normalize_transaction(raw: Dict[str, Any]) -> Transaction:
    description = str(_value(raw, "description", "Unknown transaction")).strip()
    amount = abs(float(str(_value(raw, "amount", 0)).replace(",", "").replace("₹", "").replace("Rs.", "")))
    direction_value = _value(raw, "transaction_type")
    # Some exports put the direction in the mode column. Only use it when the
    # value is an explicit direction indicator; never infer from a category.
    if direction_value in (None, ""):
        candidate_mode = str(_value(raw, "mode", "")).upper().strip()
        direction_value = candidate_mode if candidate_mode in (_CREDIT_INDICATORS | _DEBIT_INDICATORS | _TRANSFER_INDICATORS) else "DEBIT"
    transaction_type = re.sub(r"[^A-Z]", "", str(direction_value).upper())
    normalized_credit_indicators = {re.sub(r"[^A-Z]", "", value) for value in _CREDIT_INDICATORS}
    normalized_debit_indicators = {re.sub(r"[^A-Z]", "", value) for value in _DEBIT_INDICATORS}
    normalized_transfer_indicators = {re.sub(r"[^A-Z]", "", value) for value in _TRANSFER_INDICATORS}
    if transaction_type in normalized_debit_indicators:
        transaction_type = "DEBIT"
    elif transaction_type in normalized_credit_indicators:
        transaction_type = "CREDIT"
    elif transaction_type in normalized_transfer_indicators:
        transaction_type = "TRANSFER"
    else:
        transaction_type = "DEBIT"
    budget_value = str(_value(raw, "budget_status", "UNDECIDED")).upper().strip()
    budget_status = budget_value if budget_value in {"UNDECIDED", "INCLUDED", "EXCLUDED"} else "UNDECIDED"
    return Transaction(
        date=_parse_date(_value(raw, "date")),
        description=description,
        amount=amount,
        mode=str(_value(raw, "mode", "UNKNOWN")).upper(),
        transaction_type=transaction_type,
        budget_status=budget_status,
    )


def normalize_transactions(rows: Iterable[Dict[str, Any]]) -> List[Transaction]:
    return [normalize_transaction(row) for row in rows]


def parse_sms(sms_text: str) -> Transaction:
    if not sms_text or not sms_text.strip():
        raise ValueError("sms_text cannot be empty")
    text = sms_text.strip()
    amount_match = re.search(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)", text, re.I)
    if not amount_match:
        amount_match = re.search(r"(?:amount|amt)\s*[:=-]?\s*([\d,]+(?:\.\d{1,2})?)", text, re.I)
    if not amount_match:
        raise ValueError("Could not find an amount in sms_text")
    amount = float(amount_match.group(1).replace(",", ""))
    transaction_type = "CREDIT" if re.search(r"credited|credit|received|deposited", text, re.I) else "DEBIT"
    mode = "UPI" if re.search(r"upi", text, re.I) else "CARD" if re.search(r"card", text, re.I) else "UNKNOWN"
    date_match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", text)
    date = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")
    return normalize_transaction({
        "date": date,
        "description": text,
        "amount": amount,
        "mode": mode,
        "transaction_type": transaction_type,
    })
