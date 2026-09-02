"""Local verification dashboard.

Never mounted when ENVIRONMENT is production or when AUTH_REQUIRED is on. It
exists so the behaviour claimed in the architecture reports can be watched
happening rather than taken on trust.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthenticatedUser, get_current_user
from app.config import settings
from app.database import db
from app.services import ledger
from app.services.ingestion import CSVAdapter, RowsAdapter
from app.services.ingestion.service import ingest_with_adapter

router = APIRouter(prefix="/api/dev", tags=["development"])


def dev_enabled() -> bool:
    return settings.environment.lower() not in {"production", "prod"} and not settings.auth_required


def _guard() -> None:
    if not dev_enabled():
        raise HTTPException(status_code=404, detail="Not found")


def _row(day: str, description: str, amount: float, direction: str = "DEBIT", mode: str = "UPI") -> Dict[str, Any]:
    return {"date": day, "description": description, "amount": amount, "mode": mode, "transaction_type": direction}


def _csv(*lines: str) -> bytes:
    header = "date,description,amount,mode,type\n"
    return (header + "\n".join(lines) + "\n").encode()


# --- scenarios -------------------------------------------------------------
# Each returns a list of checks: (label, expected, actual). The dashboard turns
# every one into a visible pass or fail.

def scenario_accumulation(user_id: str) -> List[Dict[str, Any]]:
    ingest_with_adapter(CSVAdapter(), _csv("2026-07-01,SWIGGY ORDER,500,UPI,DEBIT"), user_id, idempotency_key="jul")
    after_first = ledger.read_aggregate(user_id)["total_spending"]
    ingest_with_adapter(CSVAdapter(), _csv("2026-08-01,UBER RIDE,300,UPI,DEBIT"), user_id, idempotency_key="aug")
    after_second = ledger.read_aggregate(user_id)
    return [
        {"label": "First import totals Rs500", "expected": 500, "actual": after_first},
        {"label": "Second import ADDS, not replaces (was Rs300 before the fix)", "expected": 800,
         "actual": after_second["total_spending"]},
        {"label": "Both months present", "expected": 2, "actual": len(after_second["monthly"])},
    ]


def scenario_same_file_twice(user_id: str) -> List[Dict[str, Any]]:
    content = _csv("2026-08-18,DOMAIN PURCHASE,348,UPI,DEBIT")
    ingest_with_adapter(CSVAdapter(), content, user_id, idempotency_key="one")
    second = ingest_with_adapter(CSVAdapter(), content, user_id, idempotency_key="two")
    rows = db.list_transactions(user_id, "CONFIRMED")
    return [
        {"label": "Re-uploading the same file creates no second transaction", "expected": 1, "actual": len(rows)},
        {"label": "Total stays Rs348", "expected": 348, "actual": ledger.read_aggregate(user_id)["total_spending"]},
        {"label": "The duplicate is kept as a second witness", "expected": 2,
         "actual": len(db.list_observations(user_id, rows[0]["id"]))},
        {"label": "Second import reports 1 duplicate", "expected": 1, "actual": second["duplicates"]},
    ]


def scenario_cross_source(user_id: str) -> List[Dict[str, Any]]:
    ingest_with_adapter(RowsAdapter("SMS"), [_row("2026-08-18", "Rs 348 debited UPI DOMAIN", 348)], user_id)
    statement = ingest_with_adapter(
        CSVAdapter(), _csv("2026-08-20,UPI-DOMAIN-PURCHASE-99887766,348,UPI,DEBIT"), user_id, idempotency_key="stmt")
    rows = db.list_transactions(user_id, "CONFIRMED")
    sources = sorted(o["source"] for o in db.list_observations(user_id, rows[0]["id"])) if rows else []
    return [
        {"label": "Phone said Rs348, bank said Rs348 -> ONE transaction", "expected": 1, "actual": len(rows)},
        {"label": "Total is Rs348, not Rs696", "expected": 348,
         "actual": ledger.read_aggregate(user_id)["total_spending"]},
        {"label": "Statement import reports 1 reconciled", "expected": 1, "actual": statement["reconciled"]},
        {"label": "Both sources recorded as witnesses", "expected": "CSV, SMS", "actual": ", ".join(sources)},
    ]


def scenario_genuine_repeats(user_id: str) -> List[Dict[str, Any]]:
    ingest_with_adapter(
        RowsAdapter("SMS"),
        [_row("2026-08-10", "CHAI STALL", 100), _row("2026-08-11", "CHAI STALL", 100)],
        user_id,
    )
    return [
        {"label": "Rs100 chai on two days stays two purchases", "expected": 2,
         "actual": len(db.list_transactions(user_id, "CONFIRMED"))},
        {"label": "Total is Rs200", "expected": 200, "actual": ledger.read_aggregate(user_id)["total_spending"]},
    ]


def scenario_near_miss(user_id: str) -> List[Dict[str, Any]]:
    ingest_with_adapter(RowsAdapter("SMS"), [_row("2026-08-18", "FUEL", 974.71, mode="CARD")], user_id)
    result = ingest_with_adapter(
        CSVAdapter(), _csv("2026-08-19,FUEL STATION,1000,CARD,DEBIT"), user_id, idempotency_key="fuel")
    queue = db.list_review_queue(user_id)
    pending = [item for item in queue if item["review_reason"] == "POSSIBLE_DUPLICATE"]
    return [
        {"label": "Rs974.71 vs Rs1000 is NOT auto-merged (would lose Rs25.29)", "expected": 1,
         "actual": len(db.list_transactions(user_id, "CONFIRMED"))},
        {"label": "and NOT auto-doubled (would invent Rs974.71)", "expected": 974.71,
         "actual": ledger.read_aggregate(user_id)["total_spending"]},
        {"label": "It is held for a human decision", "expected": 1, "actual": len(pending)},
        {"label": "The held row is excluded from totals", "expected": False,
         "actual": pending[0]["counted_in_totals"] if pending else None},
        {"label": "Import reports 1 pending review", "expected": 1, "actual": result["candidates_pending_review"]},
    ]


def scenario_unknown_merchant(user_id: str) -> List[Dict[str, Any]]:
    ingest_with_adapter(RowsAdapter("SMS"), [_row("2026-08-18", "RAHUL KUMAR", 348)], user_id)
    queue = db.list_review_queue(user_id)
    return [
        {"label": "A person's name is not silently categorised", "expected": "AMBIGUOUS",
         "actual": queue[0]["classification_status"] if queue else None},
        {"label": "It is queued for a category", "expected": "NEEDS_CATEGORY",
         "actual": queue[0]["review_reason"] if queue else None},
        {"label": "But the money still counts (hiding it would understate spending)", "expected": 348,
         "actual": ledger.read_aggregate(user_id)["total_spending"]},
        {"label": "A known merchant never reaches the queue", "expected": 1, "actual": len(queue)},
    ]


def scenario_coverage(user_id: str) -> List[Dict[str, Any]]:
    """Replays the reference spreadsheet's real shape: two blocks and a hole."""
    ingest_with_adapter(
        RowsAdapter("SMS"),
        [_row(f"2026-08-{day:02d}", "SWIGGY ORDER", 100) for day in range(9, 22)],
        user_id,
    )
    ingest_with_adapter(
        RowsAdapter("SMS"),
        [_row(f"2026-09-{day:02d}", "SWIGGY ORDER", 100) for day in range(10, 21)],
        user_id,
    )
    aggregate = ledger.read_aggregate(user_id)
    coverage, rates = aggregate["coverage"], aggregate["rates"]
    return [
        {"label": "Covered days counted honestly", "expected": 24, "actual": coverage["covered_days"]},
        {"label": "The gap between the blocks is reported, not averaged away", "expected": 19,
         "actual": coverage["gaps"][0]["days"] if coverage["gaps"] else 0},
        {"label": "Rate states its basis", "expected": "covered_days", "actual": rates["basis"]},
        {"label": "Per-day uses covered days, not the calendar span", "expected": 100.0,
         "actual": rates["spending_per_covered_day"]},
        {"label": "Uncovered days surfaced to the user", "expected": 19,
         "actual": rates["uncovered_days_in_period"]},
    ]


def scenario_transfers_and_credits(user_id: str) -> List[Dict[str, Any]]:
    ingest_with_adapter(
        RowsAdapter("SMS"),
        [
            _row("2026-08-01", "SWIGGY ORDER", 500),
            _row("2026-08-02", "SALARY CREDIT", 45000, direction="CREDIT", mode="NEFT"),
            _row("2026-08-03", "MOVE TO SAVINGS", 10000, direction="TRANSFER", mode="NEFT"),
        ],
        user_id,
    )
    aggregate = ledger.read_aggregate(user_id)
    return [
        {"label": "Salary is income, not spending", "expected": 500, "actual": aggregate["total_spending"]},
        {"label": "Credit recorded separately", "expected": 45000, "actual": aggregate["total_credit"]},
        {"label": "Transfer counts as neither", "expected": 44500, "actual": aggregate["net_cash_flow"]},
        {"label": "No Salary category in spending breakdown", "expected": None,
         "actual": aggregate["categories"].get("Salary")},
    ]


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "accumulation": {"title": "Two imports add up", "run": scenario_accumulation,
                     "note": "The defect the audit found: a second import silently replaced the first."},
    "same_file_twice": {"title": "Same file twice", "run": scenario_same_file_twice,
                        "note": "Re-upload is absorbed as another witness, not a second purchase."},
    "cross_source": {"title": "SMS then statement", "run": scenario_cross_source,
                     "note": "One lunch seen by two sources stays one transaction."},
    "genuine_repeats": {"title": "Two real chai purchases", "run": scenario_genuine_repeats,
                        "note": "Identical amounts from one source on different days are not duplicates."},
    "near_miss": {"title": "Fuel pre-auth vs settlement", "run": scenario_near_miss,
                  "note": "A close-but-unequal amount is a question, never an automatic answer."},
    "unknown_merchant": {"title": "A person's name", "run": scenario_unknown_merchant,
                         "note": "Reviewable for a category, but the amount still counts."},
    "coverage": {"title": "Coverage and gaps", "run": scenario_coverage,
                 "note": "Replays the reference spreadsheet's 13-day and 11-day blocks."},
    "transfers": {"title": "Transfers and credits", "run": scenario_transfers_and_credits,
                  "note": "Transfers are neither income nor expense."},
}


def _passed(check: Dict[str, Any]) -> bool:
    expected, actual = check["expected"], check["actual"]
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return abs(float(expected) - float(actual)) < 0.005
        except (TypeError, ValueError):
            return expected == actual
    return expected == actual


@router.get("/scenarios", summary="List available verification scenarios")
def list_scenarios(user: AuthenticatedUser = Depends(get_current_user)):
    _guard()
    return {"scenarios": [{"key": key, "title": value["title"], "note": value["note"]}
                          for key, value in SCENARIOS.items()]}


@router.post("/run/{key}", summary="Run one scenario against a clean slate")
def run_scenario(key: str, user: AuthenticatedUser = Depends(get_current_user)):
    _guard()
    if key not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Unknown scenario")
    scenario_user = f"{user.user_id}::dev::{key}"
    db.purge_user(scenario_user)
    checks = SCENARIOS[key]["run"](scenario_user)
    for check in checks:
        check["passed"] = _passed(check)
    aggregate = ledger.read_aggregate(scenario_user)
    return {
        "key": key,
        "title": SCENARIOS[key]["title"],
        "note": SCENARIOS[key]["note"],
        "checks": checks,
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
        "aggregate": {
            "total_spending": aggregate["total_spending"],
            "total_credit": aggregate["total_credit"],
            "net_cash_flow": aggregate["net_cash_flow"],
            "transaction_count": aggregate["transaction_count"],
            "categories": aggregate["categories"],
        },
        "coverage": aggregate.get("coverage", {}),
        "rates": aggregate.get("rates", {}),
        "transactions": [
            {
                "date": str(row["transaction_at"])[:10],
                "description": row.get("description"),
                "amount": row.get("amount"),
                "direction": row.get("direction"),
                "category": row.get("category_name"),
                "status": row.get("transaction_status"),
                "classification": row.get("classification_status"),
                "witnesses": len(db.list_observations(scenario_user, row["id"])),
            }
            for row in db.list_transactions(scenario_user, None)
        ],
        "review_queue": [
            {
                "description": item.get("description"),
                "amount": item.get("amount"),
                "reason": item["review_reason"],
                "counted_in_totals": item["counted_in_totals"],
            }
            for item in db.list_review_queue(scenario_user)
        ],
    }


@router.post("/run-all", summary="Run every scenario")
def run_all(user: AuthenticatedUser = Depends(get_current_user)):
    _guard()
    results = [run_scenario(key, user) for key in SCENARIOS]
    return {
        "results": results,
        "passed": sum(result["passed"] for result in results),
        "failed": sum(result["failed"] for result in results),
    }
