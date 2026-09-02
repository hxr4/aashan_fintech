from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.api.aa import router as aa_router
from app.api.auth import router as auth_router
from app.api.financial import router as financial_router
from app.api.health import router as health_router
from app.api.insights import router as insights_router
from app.api.transactions import router as transactions_router
from app.api.webhooks import router as webhook_router
from app.auth import AuthenticatedUser, get_current_user
from app.config import settings
from app.database.db import get_budgets, init_db, latest_aggregate, privacy_database_status, save_budgets
from app.services.budget import budget_status
from app.services.mock_aa import generate_mock_transactions
from app.services.pipeline import process_raw_rows


app = FastAPI(
    title=settings.app_name + " API",
    description="Privacy-first personal finance backend with Goldfish Memory.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(aa_router)
app.include_router(auth_router)
app.include_router(financial_router)
app.include_router(webhook_router)
app.include_router(transactions_router)
app.include_router(insights_router)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    @app.get("/app", include_in_schema=False)
    def frontend_entry():
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="aashan-frontend")


class BudgetRequest(BaseModel):
    budgets: Dict[str, float] = Field(default_factory=dict)


def _aggregate_or_empty(user_id: str) -> Dict[str, Any]:
    return latest_aggregate(user_id) or {
        "total_spending": 0,
        "total_debit": 0,
        "total_credit": 0,
        "net_cash_flow": 0,
        "categories": {},
        "monthly": {},
        "daily": {},
        "average_daily_spending": 0,
        "category_percentages": {},
        "transaction_count": 0,
        "weekend_vs_weekday": {"weekend": 0, "weekday": 0},
        "anomalies": [],
        "budget_status": [],
    }


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.post("/api/budgets", summary="Replace category budgets")
def set_budget(request: BudgetRequest, user: AuthenticatedUser = Depends(get_current_user)):
    if any(value < 0 for value in request.budgets.values()):
        raise HTTPException(status_code=400, detail="Budgets cannot be negative")
    save_budgets(request.budgets, user.user_id)
    aggregate = _aggregate_or_empty(user.user_id)
    aggregate["budget_status"] = budget_status(aggregate.get("categories", {}), request.budgets)
    return {"budgets": request.budgets, "status": aggregate["budget_status"]}


@app.get("/api/budgets", summary="Get configured budgets")
def list_budgets(user: AuthenticatedUser = Depends(get_current_user)):
    return {"budgets": get_budgets(user.user_id)}


@app.get("/api/budgets/status", summary="Get spending versus budget")
def get_budget_status(user: AuthenticatedUser = Depends(get_current_user)):
    aggregate = _aggregate_or_empty(user.user_id)
    return {"status": budget_status(aggregate.get("categories", {}), get_budgets(user.user_id))}


@app.get("/api/dashboard/summary", summary="Dashboard summary")
def dashboard_summary(user: AuthenticatedUser = Depends(get_current_user)):
    aggregate = _aggregate_or_empty(user.user_id)
    month = sorted(aggregate.get("monthly", {}))[-1] if aggregate.get("monthly") else None
    categories = aggregate.get("categories", {})
    top_category = max(categories, key=categories.get) if categories else None
    return {
        "total_debit": aggregate.get("total_debit", 0),
        "total_spending": aggregate.get("total_spending", 0),
        "total_credit": aggregate.get("total_credit", 0),
        "net_cash_flow": aggregate.get("net_cash_flow", 0),
        "top_category": top_category,
        "top_category_amount": categories.get(top_category, 0) if top_category else 0,
        "month": month,
        "transaction_count": aggregate.get("transaction_count", 0),
    }


@app.get("/api/dashboard/categories", summary="Category spending chart data")
def dashboard_categories(user: AuthenticatedUser = Depends(get_current_user)):
    aggregate = _aggregate_or_empty(user.user_id)
    return {"categories": aggregate.get("categories", {}), "percentages": aggregate.get("category_percentages", {})}


@app.get("/api/dashboard/monthly", summary="Monthly spending chart data")
def dashboard_monthly(user: AuthenticatedUser = Depends(get_current_user)):
    return {"monthly": _aggregate_or_empty(user.user_id).get("monthly", {})}


@app.get("/api/dashboard/patterns", summary="Daily and weekday/weekend patterns")
def dashboard_patterns(user: AuthenticatedUser = Depends(get_current_user)):
    aggregate = _aggregate_or_empty(user.user_id)
    return {"daily": aggregate.get("daily", {}), "average_daily_spending": aggregate.get("average_daily_spending", 0), "weekend_vs_weekday": aggregate.get("weekend_vs_weekday", {})}


@app.get("/api/dashboard/anomalies", summary="Anomalies without raw descriptions")
def dashboard_anomalies(user: AuthenticatedUser = Depends(get_current_user)):
    return {"anomalies": _aggregate_or_empty(user.user_id).get("anomalies", [])}


@app.get("/api/dashboard/privacy", summary="Goldfish Memory privacy status")
def dashboard_privacy(user: AuthenticatedUser = Depends(get_current_user)):
    return privacy_database_status(user.user_id)


@app.post("/api/demo/run", summary="Run the complete mock privacy demonstration")
def run_demo(user: AuthenticatedUser = Depends(get_current_user)):
    if not settings.mock_mode:
        raise HTTPException(status_code=400, detail="Demo requires MOCK_MODE=true; Setu mode never silently falls back to demo data")
    rows = generate_mock_transactions(75)
    aggregate = process_raw_rows(rows, get_budgets(user.user_id), user_id=user.user_id, source="MOCK")
    print("\n========================================\n        AASHAN PRIVACY ENGINE\n========================================\n\nTransactions processed: %d\n\nCategories generated: %d\n\nRaw transactions persisted: NO\n\nAggregate data persisted: YES\n\nAnomalies detected: %d\n\nPrivacy mode: GOLDfish MEMORY 🐟\n\n========================================\n" % (aggregate["transaction_count"], len(aggregate["categories"]), len(aggregate["anomalies"])))
    return {
        "status": "completed",
        "source": "MOCK AA DATA",
        "transactions_processed": aggregate["transaction_count"],
        "raw_transactions_persisted": False,
        "aggregate_data_persisted": True,
        "categories": aggregate["categories"],
        "total_spending": aggregate["total_spending"],
        "anomalies_detected": len(aggregate["anomalies"]),
        "privacy_mode": "GOLDFISH MEMORY",
    }
