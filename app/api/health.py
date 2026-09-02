from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment, "mock_mode": settings.mock_mode}

