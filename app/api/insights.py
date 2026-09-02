from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.auth import AuthenticatedUser, get_current_user
from app.database.db import latest_aggregate
from app.services.insights import MockInsightProvider

router = APIRouter(prefix="/api/insights", tags=["insights"])


class InsightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)


@router.post("/query", summary="Ask a question using aggregate data only")
def query_insight(request: InsightRequest, user: AuthenticatedUser = Depends(get_current_user)):
    aggregate = latest_aggregate(user.user_id)
    return {"answer": MockInsightProvider().answer(request.question, aggregate)}
