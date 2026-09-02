import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
import httpx
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user
from app.config import settings
from app.database.db import (
    get_aa_consent_context,
    get_budgets,
    save_aa_consent_context,
    update_aa_consent_status,
)
from app.services.aa_client import (
    SetuAAProvider,
    SetuConfigurationError,
    build_consent_payload,
    describe_setu_http_error,
    get_aa_provider,
    safe_setu_url,
)
from app.services.ingestion import RowsAdapter
from app.services.ingestion.service import ingest_with_adapter

router = APIRouter(prefix="/api/aa", tags=["account aggregator"])
logger = logging.getLogger(__name__)
mock_provider = get_aa_provider() if settings.mock_mode else None


class ConsentRequest(BaseModel):
    purpose: str = "Personal finance spending insights"
    mobile_number: str = "9999999999"
    data_range_from: str = "2026-06-01T00:00:00Z"
    data_range_to: str = "2026-08-31T23:59:59Z"
    purpose_code: str = "102"
    fi_types: List[str] = Field(default_factory=lambda: ["DEPOSIT"])
    consent_types: List[str] = Field(default_factory=lambda: ["TRANSACTIONS"])
    consent_duration_unit: str = "MONTH"
    consent_duration_value: int = 4
    consent_mode: str = "STORE"
    fetch_type: str = "ONETIME"
    data_life_unit: str = "MONTH"
    data_life_value: int = 1
    frequency_unit: str = "DAY"
    frequency_value: int = 1


class SessionRequest(BaseModel):
    data_range: Optional[Dict[str, str]] = None
    format: str = "json"


def _real_provider() -> SetuAAProvider:
    if settings.mock_mode:
        raise HTTPException(status_code=400, detail="Real Setu endpoints require MOCK_MODE=false")
    try:
        return SetuAAProvider()
    except SetuConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


async def _setu_call(operation, operation_name: str = "setu_operation"):
    try:
        return await operation()
    except httpx.HTTPStatusError as exc:
        if exc.response is not None:
            description = describe_setu_http_error(exc.response)
            logger.error(
                "Setu operation failed operation=%s category=%s http_status=%s details=%s",
                operation_name,
                description["category"],
                description["http_status"],
                description["message"],
            )
            raise HTTPException(status_code=502, detail={"error": "setu_api_error", **description})
        logger.error("Setu operation failed operation=%s without an HTTP response", operation_name)
        raise HTTPException(status_code=502, detail={"error": "setu_api_error", "category": "setu_http_error", "message": "Setu returned no HTTP response"})
    except httpx.TimeoutException:
        logger.error("Setu operation timed out operation=%s", operation_name)
        raise HTTPException(status_code=502, detail={"error": "setu_api_request_failed", "category": "timeout", "message": "Setu request timed out"})
    except httpx.HTTPError as exc:
        logger.error("Setu operation network error operation=%s error_type=%s", operation_name, type(exc).__name__)
        raise HTTPException(status_code=502, detail={"error": "setu_api_request_failed", "category": "network_error", "message": "Setu request failed before receiving a response"})
    except SetuConfigurationError as exc:
        logger.error("Setu operation configuration/authentication error operation=%s message=%s", operation_name, str(exc))
        raise HTTPException(status_code=502, detail={"error": "setu_api_request_failed", "category": "authentication", "message": str(exc)})


def _provider():
    try:
        return mock_provider if mock_provider is not None else get_aa_provider()
    except SetuConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/mock/consent", summary="Create a mock or Setu consent")
async def create_consent(request: ConsentRequest, user: AuthenticatedUser = Depends(get_current_user)):
    if not settings.mock_mode:
        raise HTTPException(status_code=400, detail="Mock endpoints require MOCK_MODE=true")
    response = await _provider().create_consent(request.dict())
    consent_id = response.get("id")
    if consent_id:
        save_aa_consent_context(
            consent_id,
            request.data_range_from,
            request.data_range_to,
            settings.setu_auto_fetch,
            user.user_id,
            purpose={"text": request.purpose, "code": request.purpose_code},
        )
    return response


@router.post("/consent", summary="Create a real Setu sandbox consent")
async def create_setu_consent(request: ConsentRequest, user: AuthenticatedUser = Depends(get_current_user)):
    provider = _real_provider()
    if not settings.redirect_url:
        raise HTTPException(status_code=503, detail="REDIRECT_URL must be configured for Setu consent")
    request_payload = request.model_dump()
    payload = build_consent_payload(request_payload, settings.redirect_url)
    logger.info(
        "Setu consent request prepared payload_keys=%s fi_types=%s consent_types=%s redirect_url=%s",
        sorted(payload.keys()),
        payload.get("fiTypes"),
        payload.get("consentTypes"),
        safe_setu_url(settings.redirect_url),
    )
    response = await _setu_call(lambda: provider.create_consent(payload), "create_consent")
    consent_id = response.get("id")
    consent_url = response.get("url")
    if not consent_id or not consent_url:
        raise HTTPException(status_code=502, detail="Setu consent response did not include id and url")
    save_aa_consent_context(
        consent_id,
        request.data_range_from,
        request.data_range_to,
        settings.setu_auto_fetch,
        user.user_id,
        purpose=payload.get("purpose"),
    )
    return {
        "status": "created",
        "source": provider.source_label,
        "consent_id": consent_id,
        "url": consent_url,
        "setu_status": response.get("status"),
        "data_fetched": False,
    }


@router.get("/consent/{consent_id}", summary="Get Setu consent status")
async def get_setu_consent(consent_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    context = get_aa_consent_context(consent_id)
    if not context or context.get("user_id") != user.user_id:
        raise HTTPException(status_code=404, detail="Consent not found")
    provider = _real_provider()
    response = await _setu_call(lambda: provider.get_consent_status(consent_id), "get_consent_status")
    if response.get("status"):
        update_aa_consent_status(consent_id, str(response["status"]), user.user_id)
    return {"status": "ok", "consent_id": consent_id, "data_fetched": False, "setu": response}


@router.post("/consent/{consent_id}/session", summary="Create a Setu data session")
async def create_setu_session(consent_id: str, request: SessionRequest = SessionRequest(), user: AuthenticatedUser = Depends(get_current_user)):
    provider = _real_provider()
    context = get_aa_consent_context(consent_id)
    if context and context.get("user_id") != user.user_id:
        raise HTTPException(status_code=404, detail="Consent not found")
    data_range = request.data_range or (
        {
            "from": context["data_range_from"],
            "to": context["data_range_to"],
        }
        if context
        else None
    )
    body: Dict[str, Any] = {"format": request.format}
    if data_range:
        body["dataRange"] = data_range
    response = await _setu_call(lambda: provider.create_data_session(consent_id, body), "create_data_session")
    return {
        "status": "session_created",
        "consent_id": consent_id,
        "session_id": response.get("id"),
        "data_fetched": False,
        "setu": response,
    }


@router.post("/mock/approve", summary="Approve a mock consent")
async def approve_consent(consent_id: str = Query(...), user: AuthenticatedUser = Depends(get_current_user)):
    if not settings.mock_mode:
        raise HTTPException(status_code=400, detail="Mock endpoints require MOCK_MODE=true")
    provider = _provider()
    context = get_aa_consent_context(consent_id)
    if not context or context.get("user_id") != user.user_id:
        raise HTTPException(status_code=404, detail="Consent not found")
    try:
        return await provider.approve_consent(consent_id)  # type: ignore
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/mock/fetch", summary="Create a mock session, fetch, process, and forget demo data")
async def fetch_mock_data(consent_id: str = Query(...), user: AuthenticatedUser = Depends(get_current_user)):
    if not settings.mock_mode:
        raise HTTPException(status_code=400, detail="Mock endpoints require MOCK_MODE=true")
    provider = _provider()
    context = get_aa_consent_context(consent_id)
    if not context or context.get("user_id") != user.user_id:
        raise HTTPException(status_code=404, detail="Consent not found")
    try:
        session = await provider.create_data_session(consent_id)
        rows = await provider.fetch_data(session["id"])
        result = ingest_with_adapter(
            RowsAdapter("SETU"),
            rows,
            user.user_id,
            idempotency_key=f"mock-session:{session['id']}",
            budgets=get_budgets(user.user_id),
        )
        return {"status": "processed", "source": provider.source_label, "session": session, "aggregate": result["aggregate"], "raw_transactions_persisted": False}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/callback", summary="Setu redirect callback")
async def callback(request: Request):
    params = dict(request.query_params)
    consent_id = params.get("id")
    success_value = params.get("success")
    success = success_value.lower() == "true" if success_value is not None else None
    error = None
    if success is False:
        error = {
            "code": params.get("errorcode"),
            "message": params.get("errormsg"),
        }
        if consent_id:
            update_aa_consent_status(consent_id, "REJECTED")
        return {
            "status": "rejected",
            "consent_id": consent_id,
            "data_fetched": False,
            "error": error,
            "parameters_received": sorted(params),
        }
    if consent_id:
        update_aa_consent_status(consent_id, "APPROVED_CALLBACK")
    return {
        "status": "approved_pending_processing" if success is True else "callback_received",
        "consent_id": consent_id,
        "data_fetched": False,
        "message": "Consent callback received. Setu notification processing will determine when data is available.",
        "parameters_received": sorted(params),
    }
