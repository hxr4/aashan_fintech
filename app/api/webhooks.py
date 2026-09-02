from datetime import datetime
import json
import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.api.aa import mock_provider
from app.auth import LOCAL_USER_ID
from app.config import settings
from app.database.db import (
    aa_session_processed,
    aa_webhook_event_processed,
    get_aa_consent_context,
    get_budgets,
    mark_aa_session_processed,
    mark_aa_webhook_event,
    update_aa_consent_status,
)
from app.services.aa_client import SetuAAProvider, SetuConfigurationError, describe_setu_http_error, safe_setu_text
from app.services import webhook_auth
from app.services.mock_aa import generate_mock_transactions
from app.services.pipeline import process_raw_rows
from app.services.ingestion import SetuAdapter
from app.services.ingestion.service import ingest_with_adapter


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)
_SUPPORTED_EVENTS = {"CONSENT_STATUS_UPDATE", "SESSION_STATUS_UPDATE", "FI_DATA_READY"}
_READY_STATUSES = {"PARTIAL", "COMPLETED"}


def _status(payload: Dict[str, Any]) -> Optional[str]:
    data = payload.get("data")
    nested_status = data.get("status") if isinstance(data, dict) else None
    value = nested_status or payload.get("status")
    return str(value).upper() if value else None


def _session_id(payload: Dict[str, Any]) -> Optional[str]:
    data = payload.get("data")
    nested = data.get("dataSessionId") if isinstance(data, dict) else None
    return payload.get("dataSessionId") or nested or payload.get("sessionId")


def _event_key(payload: Dict[str, Any], event_type: str, consent_id: str, session_id: Optional[str], status: Optional[str]) -> str:
    return str(payload.get("notificationId") or ":".join([event_type, consent_id, session_id or "", status or ""]))


def _safe_webhook_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)[:300]


def _safe_webhook_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return safe_setu_text(value, limit=300)


def _log_webhook_diagnostics(payload: Dict[str, Any]) -> None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    error = payload.get("error") if isinstance(payload.get("error"), dict) else data.get("error") if isinstance(data.get("error"), dict) else {}
    event_type = payload.get("type") or payload.get("eventType") or payload.get("event")
    session_id = payload.get("sessionId") or data.get("sessionId")
    data_session_id = payload.get("dataSessionId") or data.get("dataSessionId")
    error_code = payload.get("errorCode") or payload.get("errorcode") or error.get("code")
    error_message = payload.get("errorMessage") or payload.get("errormsg") or error.get("message")
    logger.info(
        "Setu webhook received event=%s type=%s top_level_keys=%s consent_id=%s session_id=%s data_session_id=%s error_code=%s error_message=%s",
        _safe_webhook_text(payload.get("event")),
        _safe_webhook_text(event_type),
        sorted(str(key) for key in payload.keys()),
        _safe_webhook_id(payload.get("consentId")),
        _safe_webhook_id(session_id),
        _safe_webhook_id(data_session_id),
        _safe_webhook_text(error_code),
        _safe_webhook_text(error_message),
    )


async def _setu_provider() -> SetuAAProvider:
    if settings.mock_mode:
        raise HTTPException(status_code=400, detail="Setu webhooks require MOCK_MODE=false")
    try:
        return SetuAAProvider()
    except SetuConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


async def _fetch_setu_data(provider: SetuAAProvider, session_id: str) -> Dict[str, Any]:
    try:
        return await provider.fetch_data(session_id)
    except httpx.HTTPStatusError as exc:
        # The upstream body can carry account identifiers and tokens; only the
        # allow-listed diagnostic fields are ever surfaced or logged.
        description = describe_setu_http_error(exc.response) if exc.response is not None else {}
        logger.error("provider data fetch failed category=%s http_status=%s",
                     description.get("category"), description.get("http_status"))
        raise HTTPException(status_code=502, detail={"error": "provider_fetch_failed",
                                                     "category": description.get("category", "unknown")})
    except httpx.HTTPError as exc:
        logger.error("provider data fetch network error error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail={"error": "provider_fetch_failed", "category": "network_error"})


async def _create_setu_session(consent_id: str) -> Dict[str, Any]:
    provider = await _setu_provider()
    context = get_aa_consent_context(consent_id)
    body: Dict[str, Any] = {"format": "json"}
    if context:
        body["dataRange"] = {"from": context["data_range_from"], "to": context["data_range_to"]}
    try:
        return await provider.create_data_session(consent_id, body)
    except httpx.HTTPStatusError as exc:
        description = describe_setu_http_error(exc.response) if exc.response is not None else {}
        logger.error("provider session creation failed category=%s http_status=%s",
                     description.get("category"), description.get("http_status"))
        raise HTTPException(status_code=502, detail={"error": "provider_session_failed",
                                                     "category": description.get("category", "unknown")})
    except httpx.HTTPError as exc:
        logger.error("provider session creation network error error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail={"error": "provider_session_failed", "category": "network_error"})


def _validate_notification(payload: Dict[str, Any]) -> tuple[str, str]:
    # Validation is limited to the documented sandbox JSON contract. No
    # undocumented signature or shared-secret scheme is invented here.
    event_type = str(payload.get("type", "")).upper()
    consent_id = payload.get("consentId")
    if event_type not in _SUPPORTED_EVENTS:
        logger.warning(
            "Setu webhook rejected reason=unsupported_type received_type=%s top_level_keys=%s",
            _safe_webhook_text(event_type),
            sorted(str(key) for key in payload.keys()),
        )
        raise HTTPException(status_code=400, detail="Unsupported Setu notification type")
    if not consent_id:
        logger.warning(
            "Setu webhook rejected reason=missing_consent_id type=%s top_level_keys=%s",
            _safe_webhook_text(event_type),
            sorted(str(key) for key in payload.keys()),
        )
        raise HTTPException(status_code=400, detail="Setu notification is missing consentId")
    return event_type, str(consent_id)


async def _process_setu_transactions(
    payload: Dict[str, Any],
    event_key: str,
    event_type: str,
    consent_id: str,
    session_id: Optional[str],
    user_id: str,
) -> Dict[str, Any]:
    if session_id and aa_session_processed(session_id):
        return {"processed": False, "duplicate": True, "session_id": session_id}
    result = ingest_with_adapter(
        SetuAdapter(),
        payload,
        user_id,
        idempotency_key=f"session:{session_id}" if session_id else f"notification:{event_key}",
        budgets=get_budgets(user_id),
    )
    if result.get("status") == "already_processed":
        return {"processed": False, "duplicate": True, "session_id": session_id}
    if result.get("rows_received", 0) == 0:
        return {"processed": False, "data_available": False, "session_id": session_id}
    aggregate = result.get("aggregate") or {}
    if session_id:
        mark_aa_session_processed(session_id)
    mark_aa_webhook_event(event_key, event_type, consent_id, session_id)
    return {
        "processed": True,
        "duplicate": False,
        "session_id": session_id,
        "import_id": result.get("import_id"),
        "aggregate_summary": {
            "total_spending": aggregate["total_spending"],
            "total_credit": aggregate["total_credit"],
            "transaction_count": aggregate["transaction_count"],
        },
    }


@router.post("/setu", summary="Receive authenticated consent and FI session notifications")
async def setu_webhook(request: Request):
    body = await request.body()
    if len(body) > settings.max_webhook_bytes:
        raise HTTPException(status_code=413, detail="Webhook payload too large")
    # Authenticate before parsing: never let an unauthenticated caller reach the
    # ingestion path, and never spend work on a body we have not vouched for.
    auth_method = webhook_auth.enforce(request, body)
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Webhook body is not valid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object")
    logger.info("webhook authenticated via=%s", auth_method)
    _log_webhook_diagnostics(payload)
    event_type, consent_id = _validate_notification(payload)
    status = _status(payload)
    session_id = _session_id(payload)
    timestamp = payload.get("timestamp", datetime.utcnow().isoformat())
    consent_context = get_aa_consent_context(consent_id)
    if not consent_context and settings.auth_required:
        raise HTTPException(status_code=404, detail="Unknown Setu consent")
    owner_user_id = (consent_context or {}).get("user_id") or LOCAL_USER_ID

    if payload.get("success") is False:
        update_aa_consent_status(consent_id, status or "ERROR", owner_user_id)
        return {
            "accepted": True,
            "processed": False,
            "event_type": event_type,
            "consent_id": consent_id,
            "status": status,
            "error": payload.get("error"),
            "timestamp": timestamp,
        }

    # Keep the existing mock behavior isolated from the real Setu provider.
    if settings.mock_mode:
        if mock_provider is not None and consent_id in mock_provider.consents:
            if event_type == "CONSENT_STATUS_UPDATE" and status:
                mock_provider.consents[consent_id]["status"] = status
            if event_type == "SESSION_STATUS_UPDATE" and session_id in mock_provider.sessions:
                mock_provider.sessions[session_id]["status"] = status
            if event_type == "FI_DATA_READY" and status in {"READY", "PARTIAL", "COMPLETED"}:
                aggregate = process_raw_rows(
                    generate_mock_transactions(),
                    get_budgets(owner_user_id),
                    user_id=owner_user_id,
                    source="SETU_MOCK",
                )
                return {
                    "accepted": True,
                    "processed": True,
                    "event_type": event_type,
                    "consent_id": consent_id,
                    "status": status,
                    "timestamp": timestamp,
                    "aggregate_summary": {
                        "total_spending": aggregate["total_spending"],
                        "transaction_count": aggregate["transaction_count"],
                    },
                }
        return {"accepted": True, "processed": False, "event_type": event_type, "consent_id": consent_id, "status": status, "timestamp": timestamp}

    event_key = _event_key(payload, event_type, consent_id, session_id, status)
    if aa_webhook_event_processed(event_key):
        return {"accepted": True, "processed": False, "duplicate": True, "event_type": event_type, "consent_id": consent_id, "status": status, "timestamp": timestamp}

    update_aa_consent_status(consent_id, status or "RECEIVED", owner_user_id)

    if event_type == "CONSENT_STATUS_UPDATE":
        session = None
        if status in {"ACTIVE", "APPROVED"} and not settings.setu_auto_fetch:
            session = await _create_setu_session(consent_id)
            mark_aa_webhook_event(event_key, event_type, consent_id, session.get("id"))
        else:
            mark_aa_webhook_event(event_key, event_type, consent_id, None)
        return {
            "accepted": True,
            "processed": False,
            "event_type": event_type,
            "consent_id": consent_id,
            "status": status,
            "session_created": bool(session),
            "session_id": session.get("id") if session else None,
            "data_fetched": False,
            "timestamp": timestamp,
        }

    if event_type == "SESSION_STATUS_UPDATE" and status in _READY_STATUSES and session_id:
        provider = await _setu_provider()
        data = await _fetch_setu_data(provider, session_id)
        result = await _process_setu_transactions(data, event_key, event_type, consent_id, session_id, owner_user_id)
        result.update({"accepted": True, "event_type": event_type, "consent_id": consent_id, "status": status, "timestamp": timestamp})
        return result

    if event_type == "FI_DATA_READY" and status in _READY_STATUSES:
        result = await _process_setu_transactions(payload, event_key, event_type, consent_id, session_id, owner_user_id)
        result.update({"accepted": True, "event_type": event_type, "consent_id": consent_id, "status": status, "timestamp": timestamp})
        return result

    mark_aa_webhook_event(event_key, event_type, consent_id, session_id)
    return {"accepted": True, "processed": False, "event_type": event_type, "consent_id": consent_id, "status": status, "timestamp": timestamp}
