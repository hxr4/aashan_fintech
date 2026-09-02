from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthenticatedUser, require_supabase_user
from app.config import settings
from app.database import db
from app.services import ledger


router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/config", summary="Return safe Supabase client configuration")
def auth_config():
    """The anon key is client-safe; service-role credentials are never returned."""
    return {
        "provider": "supabase",
        "supabase_url": settings.supabase_url,
        "supabase_anon_key": settings.supabase_anon_key,
        "auth_required": settings.auth_required,
        "providers": ["password", "google"],
    }


@router.get("/session", summary="Validate the current Supabase session")
def session(user: AuthenticatedUser = Depends(require_supabase_user)):
    return {"authenticated": True, "user_id": user.user_id, "email": user.email}


@router.post("/logout", summary="Acknowledge client-side Supabase logout")
def logout(user: AuthenticatedUser = Depends(require_supabase_user)):
    """Supabase owns the session token; the client must clear/revoke it.

    The backend does not receive or persist passwords or refresh tokens.
    """
    return {"status": "logout_required_on_client", "user_id": user.user_id}


@router.delete("/account", summary="Delete every trace of this account's financial data")
def delete_account(user: AuthenticatedUser = Depends(require_supabase_user)):
    """Actually delete, rather than returning 501.

    A product that claims your data is yours has to be able to give it back and
    throw it away. Removal is owner-scoped and covers every table that carries a
    user_id, child rows first.

    Supabase owns the credential record itself; clearing that is a separate call
    with the service-role key, and the response says plainly whether it happened
    rather than implying more than was done.
    """
    removed = db.purge_user(user.user_id)
    db.record_privacy_event(user.user_id, "ACCOUNT_DATA_DELETED", {"tables": sorted(removed)})
    return {
        "status": "deleted",
        "rows_removed": removed,
        "total_rows_removed": sum(removed.values()),
        "identity_record_removed": False,
        "note": (
            "All financial data for this account has been removed from Aashan. "
            "The Supabase identity record is managed separately and is not deleted by this call."
        ),
    }


@router.get("/export", summary="Export everything held for this account", include_in_schema=True)
def export_account(user: AuthenticatedUser = Depends(require_supabase_user)):
    return _export(user.user_id)


def _export(user_id: str) -> dict:
    transactions = db.list_transactions(user_id, None)
    return {
        "user_id": user_id,
        "transactions": transactions,
        "observations": {
            row["id"]: db.list_observations(user_id, row["id"]) for row in transactions
        },
        "imports": db.list_imports(user_id),
        "coverage": db.list_coverage(user_id),
        "budgets": db.get_budgets(user_id),
        "merchant_rules": db.list_merchant_rules(user_id),
        "aggregate": ledger.read_aggregate(user_id),
    }
