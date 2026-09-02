import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.auth import AuthenticatedUser, get_current_user
from app.database.db import get_budgets
from app.services.normalizer import parse_sms
from app.services.categorizer import Categorizer
from app.services.ingestion import CSVAdapter, RowsAdapter
from app.services.ingestion.service import ingest_with_adapter
from app.services.ingestion import worker
from app.database import db

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])
logger = logging.getLogger(__name__)


class SMSRequest(BaseModel):
    sms_text: str


@router.post("/sms", summary="Ingest one SMS without retaining the SMS text")
def ingest_sms(request: SMSRequest, user: AuthenticatedUser = Depends(get_current_user)):
    try:
        transaction = parse_sms(request.sms_text)
        # SMS used to call the processing kernel directly, so it never produced a
        # canonical transaction. It now enters the same pipeline as every other
        # source, which is what makes cross-source reconciliation possible.
        result = ingest_with_adapter(
            RowsAdapter("SMS"),
            [{
                "date": transaction.date.isoformat(),
                "description": transaction.description,
                "amount": transaction.amount,
                "mode": transaction.mode,
                "transaction_type": transaction.transaction_type,
            }],
            user.user_id,
            budgets=get_budgets(user.user_id),
        )
        category = Categorizer().categorize(transaction)
        return {"status": "processed", "category": category or "Other", "aggregate": result["aggregate"]}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# A CSV of a year of statements is a few hundred kilobytes. Anything far past
# that is either a mistake or an attempt to exhaust memory, and the body is read
# in chunks so an oversized upload is refused before it is all in RAM.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_CHUNK = 64 * 1024


async def _read_bounded(file: UploadFile, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise HTTPException(status_code=413, detail=f"File exceeds the {limit // (1024 * 1024)} MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/csv", summary="Ingest a CSV through the canonical pipeline")
async def ingest_csv(
    file: UploadFile = File(...),
    background: bool = Query(default=False, description="Return a job id immediately instead of waiting"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AuthenticatedUser = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    content = await _read_bounded(file)
    budgets = get_budgets(user.user_id)

    def run() -> dict:
        return ingest_with_adapter(
            CSVAdapter(),
            content,
            user.user_id,
            filename=file.filename,
            idempotency_key=idempotency_key,
            budgets=budgets,
        )

    if background:
        worker.submit(run, user_id=user.user_id, job_label=f"csv:{file.filename}")
        return {"status": "accepted", "background": True,
                "message": "Processing started. Poll /api/jobs to follow it."}

    try:
        # Off the event loop: this does blocking database work and may load a
        # classifier, neither of which belongs on the loop that serves everyone.
        return await run_in_threadpool(run)
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        logger.info("CSV ingestion rejected filename=%s error_type=%s", file.filename, type(exc).__name__)
        raise HTTPException(status_code=400, detail="Invalid CSV input")
    except Exception:
        logger.exception("CSV ingestion failed filename=%s", file.filename)
        raise HTTPException(status_code=500, detail="CSV processing failed")
