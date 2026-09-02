"""One timezone, applied everywhere, so month buckets never shift.

Dates arrived as naive datetimes while PostgreSQL columns are timestamptz, so a
value written in one place was reinterpreted in the server's zone in another. A
transaction at 23:40 on the 31st could land in the following month's total.
Aashan is INR-first and India-first, so Asia/Kolkata is the anchor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except Exception:  # pragma: no cover - fallback when tzdata is unavailable
    from datetime import timedelta

    IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def to_ist(value: Any) -> datetime:
    """Return an Asia/Kolkata-aware datetime.

    A naive value is assumed to already be a local Indian wall-clock time, which
    is what a bank statement or an SMS actually contains. An aware value is
    converted, never reinterpreted.
    """
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value).strip()
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        return moment.replace(tzinfo=IST)
    return moment.astimezone(IST)


def now_ist() -> datetime:
    return datetime.now(tz=IST)
