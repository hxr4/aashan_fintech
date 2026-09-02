"""Deciding whether two observations describe the same real-world transaction.

Money is never fuzzy-matched. Amount and direction must agree exactly; only the
date is allowed a tolerance, because a card authorisation and its settlement are
the same purchase seen on different days.

Two rules, in order of confidence:

1. Content hash -- same owner, account, calendar day, direction, amount and
   normalised description. This catches re-uploading the same statement or the
   same CSV twice.
2. Cross-source window -- same owner, account, direction and exact amount within
   a few days, where the incoming observation comes from a source that has not
   already been seen on that transaction. Two identical amounts from the *same*
   source on different days are two real purchases, not a duplicate, so that
   case deliberately does not merge.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Optional

# A card authorisation can settle up to three days later. UPI is same-day in
# practice, but a single window keeps the rule explainable.
DEFAULT_WINDOW_DAYS = 3

_NOISE = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")
# Long digit runs are reference numbers, which differ between an SMS alert and
# the statement line for the very same purchase.
_LONG_DIGITS = re.compile(r"\b\d{6,}\b")


def normalized_description(value: Optional[str]) -> str:
    text = (value or "").upper()
    text = _LONG_DIGITS.sub("", text)
    text = _NOISE.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def amount_key(amount: float) -> str:
    """Money compared in paise, so 100.00 and 100.001 never disagree."""
    return str(int(round(float(amount) * 100)))


def content_hash(
    user_id: str,
    account_id: Optional[str],
    transaction_at: datetime,
    direction: str,
    amount: float,
    description: Optional[str],
) -> str:
    parts = [
        user_id,
        account_id or "-",
        transaction_at.strftime("%Y-%m-%d"),
        (direction or "DEBIT").upper(),
        amount_key(amount),
        normalized_description(description),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
