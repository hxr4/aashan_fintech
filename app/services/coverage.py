"""What the ledger could and could not see.

The reference spreadsheet that motivated this feature reported "about Rs 333/day
or Rs 3,663/month" in one sentence. The first figure divides by the 22 days on
which a meal was recorded; the second divides by two calendar months, 36 days of
which held no data at all. They are 2.8x apart, and the benchmark conclusion
drawn from the smaller one was therefore backwards.

Automating ingestion does not remove partial coverage, it moves it: a statement
covers a known window, SMS covers from the day the app was installed, and cash
covers nothing unless somebody types it in. So coverage is a stored dimension,
and every rate this system publishes carries the days it was divided by.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

DAYS_PER_MONTH = 30.44


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    return datetime.fromisoformat(text.replace("Z", "+00:00")).date()


def merge_ranges(ranges: Iterable[Tuple[date, date]]) -> List[Tuple[date, date]]:
    """Collapse overlapping and touching windows into a minimal set."""
    ordered = sorted((start, end) for start, end in ranges if start <= end)
    merged: List[Tuple[date, date]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1] + timedelta(days=1):
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def covered_days(ranges: Iterable[Tuple[date, date]]) -> int:
    return sum((end - start).days + 1 for start, end in merge_ranges(ranges))


def gaps(ranges: Iterable[Tuple[date, date]]) -> List[Dict[str, Any]]:
    """The holes between the first and last thing we saw."""
    merged = merge_ranges(ranges)
    result: List[Dict[str, Any]] = []
    for previous, following in zip(merged, merged[1:]):
        gap_start = previous[1] + timedelta(days=1)
        gap_end = following[0] - timedelta(days=1)
        if gap_start <= gap_end:
            result.append({
                "from": gap_start.isoformat(),
                "to": gap_end.isoformat(),
                "days": (gap_end - gap_start).days + 1,
            })
    return result


def summarize(windows: List[Dict[str, Any]], days_with_transactions: int = 0) -> Dict[str, Any]:
    ranges = [(_as_date(w["covered_from"]), _as_date(w["covered_to"])) for w in windows]
    merged = merge_ranges(ranges)
    total_days = covered_days(ranges)
    by_source: Dict[str, List[Tuple[date, date]]] = {}
    for window in windows:
        by_source.setdefault(window["source"], []).append(
            (_as_date(window["covered_from"]), _as_date(window["covered_to"]))
        )
    return {
        "covered_days": total_days,
        "days_with_transactions": days_with_transactions,
        "first_covered": merged[0][0].isoformat() if merged else None,
        "last_covered": merged[-1][1].isoformat() if merged else None,
        "gaps": gaps(ranges),
        "sources": sorted(
            (
                {
                    "source": source,
                    "covered_days": covered_days(source_ranges),
                    "from": merge_ranges(source_ranges)[0][0].isoformat(),
                    "to": merge_ranges(source_ranges)[-1][1].isoformat(),
                }
                for source, source_ranges in by_source.items()
            ),
            key=lambda item: item["source"],
        ),
    }


def rates(total_spending: float, coverage: Dict[str, Any]) -> Dict[str, Any]:
    """Every rate states the denominator it used. No denominator, no rate."""
    days = coverage.get("covered_days") or 0
    if not days:
        return {
            "basis": "no_coverage",
            "covered_days": 0,
            "spending_per_covered_day": None,
            "projected_monthly": None,
            "explanation": "No source has covered any period yet, so no daily or monthly rate can be stated.",
        }
    per_day = round(float(total_spending) / days, 2)
    gap_days = sum(gap["days"] for gap in coverage.get("gaps", []))
    explanation = f"Rs {per_day:,.2f} per day across {days} covered day(s)."
    if gap_days:
        explanation += f" {gap_days} day(s) inside the period were not covered by any source."
    return {
        "basis": "covered_days",
        "covered_days": days,
        "uncovered_days_in_period": gap_days,
        "spending_per_covered_day": per_day,
        "projected_monthly": round(per_day * DAYS_PER_MONTH, 2),
        "explanation": explanation,
    }
