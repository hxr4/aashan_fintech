import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import AuthenticatedUser, get_current_user
from app.database.db import get_budgets
from app.services.pipeline import process_raw_rows
from app.services.normalizer import parse_sms
from app.services.categorizer import Categorizer
from app.services.ingestion import CSVAdapter
from app.services.ingestion.service import ingest_with_adapter

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])
logger = logging.getLogger(__name__)


class SMSRequest(BaseModel):
    sms_text: str


@router.post("/sms", summary="Ingest one SMS without retaining the SMS text")
def ingest_sms(request: SMSRequest, user: AuthenticatedUser = Depends(get_current_user)):
    try:
        transaction = parse_sms(request.sms_text)
        transaction.category = Categorizer().categorize(transaction)
        aggregate = process_raw_rows(
            [transaction.dict()],
            get_budgets(user.user_id),
            user_id=user.user_id,
            source="SMS",
        )
        return {"status": "processed", "category": transaction.category or "Other", "aggregate": aggregate}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/csv", summary="Ingest a CSV and persist only aggregate results")
async def ingest_csv(
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AuthenticatedUser = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    content = await file.read()
    try:
        result = ingest_with_adapter(
            CSVAdapter(),
            content,
            user.user_id,
            filename=file.filename,
            idempotency_key=idempotency_key,
            budgets=get_budgets(user.user_id),
        )
        return result
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        logger.info("CSV ingestion rejected filename=%s error_type=%s", file.filename, type(exc).__name__)
        raise HTTPException(status_code=400, detail="Invalid CSV input")
    except Exception as exc:
        logger.exception("CSV ingestion failed filename=%s error_type=%s", file.filename, type(exc).__name__)
        raise HTTPException(status_code=500, detail="CSV processing failed")
