from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthenticatedUser, require_supabase_user
from app.config import settings


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


@router.delete("/account", summary="Delete the authenticated Aashan account data")
def delete_account(user: AuthenticatedUser = Depends(require_supabase_user)):
    if not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=501,
            detail="Account deletion requires the server-side Supabase service-role configuration",
        )
    raise HTTPException(
        status_code=501,
        detail="Supabase user deletion workflow is reserved for the privacy deletion implementation",
    )
