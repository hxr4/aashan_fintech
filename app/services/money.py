"""Money is added exactly, then presented.

Amounts were Python floats, SQLite stored REAL and PostgreSQL stores
NUMERIC(18,2), so development and production could disagree on a rounded total.
Accumulating thousands of float rows also drifts. Every sum in this system runs
through Decimal and is quantised once, at the end, half-up like a bank.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


def to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ZERO


def quantize(value: Any) -> Decimal:
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def total(values: Iterable[Any]) -> Decimal:
    result = ZERO
    for value in values:
        result += to_decimal(value)
    return result


def as_float(value: Any) -> float:
    """Presentation only. Never feed this back into another sum."""
    return float(quantize(value))
