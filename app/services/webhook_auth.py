"""Nobody may write to a user's ledger by knowing a consent ID.

The webhook previously validated only that `type` was in a three-item set and
that `consentId` was present. With MOCK_MODE=false and a public URL, anyone who
learned or guessed a consent ID could POST FI_DATA_READY with an arbitrary
payload and have canonical transactions written to that owner's account.

Two independent controls, either of which is sufficient, both of which the
provider is told about at onboarding:

* a bearer token the provider presents -- this is the shape Finvu uses, where
  the FIU generates a token and shares it for callback authentication
* an HMAC-SHA256 signature over the raw body with a timestamp, which additionally
  proves the body was not altered and bounds replay

The endpoint fails closed. If neither is configured outside mock mode it refuses
every request rather than quietly accepting them.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Optional, Tuple

from fastapi import HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-Aashan-Signature"
TOKEN_HEADER = "X-Aashan-Webhook-Token"


class WebhookRejected(Exception):
    def __init__(self, reason: str, status_code: int = 401) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


def _presented_token(request: Request) -> str:
    header = request.headers.get(TOKEN_HEADER)
    if header:
        return header.strip()
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _parse_signature(value: str) -> Tuple[Optional[int], Optional[str]]:
    timestamp: Optional[int] = None
    digest: Optional[str] = None
    for part in value.split(","):
        key, _, raw = part.strip().partition("=")
        if key == "t":
            try:
                timestamp = int(raw)
            except ValueError:
                return None, None
        elif key == "v1":
            digest = raw
    return timestamp, digest


def expected_signature(secret: str, timestamp: int, body: bytes) -> str:
    payload = str(timestamp).encode() + b"." + body
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def sign(secret: str, body: bytes, timestamp: Optional[int] = None) -> str:
    """Build a header value. Used by tests and by any provider simulator."""
    moment = int(time.time()) if timestamp is None else timestamp
    return f"t={moment},v1={expected_signature(secret, moment, body)}"


def verify(request: Request, body: bytes) -> str:
    """Return the control that authenticated this call, or raise."""
    if settings.mock_mode and not (settings.aa_webhook_token or settings.aa_webhook_secret):
        return "mock_mode"

    if not settings.aa_webhook_token and not settings.aa_webhook_secret:
        # Fail closed. An unauthenticated write path into somebody's financial
        # history is not something to leave open because configuration is missing.
        raise WebhookRejected("webhook authentication is not configured", status_code=503)

    if settings.aa_webhook_secret:
        raw = request.headers.get(SIGNATURE_HEADER, "")
        if not raw:
            raise WebhookRejected("missing signature")
        timestamp, digest = _parse_signature(raw)
        if timestamp is None or not digest:
            raise WebhookRejected("malformed signature")
        drift = abs(int(time.time()) - timestamp)
        if drift > settings.webhook_replay_window_seconds:
            raise WebhookRejected("signature timestamp outside the replay window")
        if not hmac.compare_digest(expected_signature(settings.aa_webhook_secret, timestamp, body), digest):
            raise WebhookRejected("signature mismatch")
        return "hmac"

    if not hmac.compare_digest(_presented_token(request), settings.aa_webhook_token):
        raise WebhookRejected("invalid webhook token")
    return "token"


def enforce(request: Request, body: bytes) -> str:
    try:
        method = verify(request, body)
    except WebhookRejected as rejection:
        # Log why, never what: the body is somebody's financial data.
        logger.warning(
            "webhook rejected reason=%s client=%s bytes=%d",
            rejection.reason,
            request.client.host if request.client else "unknown",
            len(body),
        )
        raise HTTPException(status_code=rejection.status_code, detail="Webhook authentication failed")
    return method
