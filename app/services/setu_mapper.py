from typing import Any, Dict, Iterable, List


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _transaction_rows(account: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    transactions = account.get("transactions") or {}
    return _as_list(transactions.get("transaction"))


def _account_rows(account: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for transaction in _transaction_rows(account):
        if not isinstance(transaction, dict):
            continue
        row = {
            "date": transaction.get("valueDate") or transaction.get("transactionTimestamp") or transaction.get("date"),
            "description": transaction.get("narration") or transaction.get("description") or "Setu transaction",
            "amount": transaction.get("amount", 0),
            "mode": transaction.get("mode", "UNKNOWN"),
            "transaction_type": transaction.get("type") or transaction.get("transactionType"),
        }
        external_id = transaction.get("txnId") or transaction.get("transactionId") or transaction.get("transaction_id") or transaction.get("reference")
        if external_id:
            row["external_id"] = external_id
        yield row


def flatten_setu_transactions(payload: Any) -> List[Dict[str, Any]]:
    """Flatten manual-session and auto-fetch Setu FI responses into raw rows.

    Only transaction fields are copied. Account profile, balances, PAN, mobile,
    and other FI metadata never enter the existing processing pipeline.
    """
    rows: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        payload = {"rows": payload}
    if not isinstance(payload, dict):
        return rows

    for row in _as_list(payload.get("rows")):
        if isinstance(row, dict):
            rows.append(row)

    for fip in _as_list(payload.get("fips")):
        if not isinstance(fip, dict):
            continue
        for account_entry in _as_list(fip.get("accounts")):
            if not isinstance(account_entry, dict):
                continue
            account_data = account_entry.get("data") or {}
            account = account_data.get("account") if isinstance(account_data, dict) else None
            if isinstance(account, dict):
                rows.extend(_account_rows(account))

    for fip in _as_list(payload.get("fiData")):
        if not isinstance(fip, dict):
            continue
        for data_entry in _as_list(fip.get("data")):
            if not isinstance(data_entry, dict):
                continue
            decrypted = data_entry.get("decryptedFI") or data_entry.get("data") or {}
            account = decrypted.get("account") if isinstance(decrypted, dict) else None
            if isinstance(account, dict):
                rows.extend(_account_rows(account))

    return rows
