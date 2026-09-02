from abc import ABC, abstractmethod
import json
import logging
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import httpx

from app.config import settings
from app.services.mock_aa import MockAAProvider


logger = logging.getLogger(__name__)

_SAFE_ERROR_KEYS = {
    "code",
    "detail",
    "error",
    "errorcode",
    "error_code",
    "errormessage",
    "error_message",
    "errormsg",
    "error_msg",
    "message",
    "status",
    "title",
    "traceid",
    "trace_id",
}
_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)bearer\s+[^\s,;]+|\b\d{8,}\b|(?<![A-Za-z0-9])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9])"
)


def safe_setu_text(value: Any, limit: int = 500) -> str:
    """Redact token-like, account-like, and long numeric values in diagnostics."""
    text = str(value)
    return _SENSITIVE_VALUE_RE.sub("[REDACTED]", text)[:limit]


def safe_setu_url(url: Any) -> str:
    """Return only the non-sensitive parts of a URL for diagnostics."""
    parsed = urlsplit(str(url))
    if not parsed.scheme or not parsed.hostname:
        return "<invalid-url>"
    host = parsed.hostname
    try:
        if parsed.port:
            host += f":{parsed.port}"
    except ValueError:
        return "<invalid-url>"
    return f"{parsed.scheme}://{host}{parsed.path}"


def safe_setu_error_details(response: httpx.Response) -> Dict[str, str]:
    """Extract allow-listed error fields without logging an arbitrary response body."""
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        return {"message": response.reason_phrase or "non-JSON Setu error body omitted"}

    details: Dict[str, str] = {}

    def collect(value: Any) -> None:
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            normalized_key = str(key).lower().replace("-", "_")
            if normalized_key not in _SAFE_ERROR_KEYS:
                continue
            if isinstance(child, (str, int, float, bool)):
                details[str(key)] = safe_setu_text(child)
            elif isinstance(child, dict):
                collect(child)

    collect(body)
    return details or {"message": "Setu returned an error without a safe diagnostic message"}


def classify_setu_http_error(response: httpx.Response) -> str:
    """Classify a Setu response using status and allow-listed error text."""
    details = safe_setu_error_details(response)
    message = " ".join(details.values()).lower()
    status_code = response.status_code
    if status_code == 401:
        return "authentication"
    if status_code == 403:
        return "invalid_product_instance" if "product" in message else "invalid_client_credentials"
    if status_code == 404:
        return "invalid_product_instance" if "product instance" in message else "wrong_setu_api_url_or_resource"
    if status_code in {400, 422}:
        if any(term in message for term in ("product instance", "product_instance")):
            return "invalid_product_instance"
        if any(term in message for term in ("client", "credential", "secret", "authentication")):
            return "invalid_client_credentials"
        return "invalid_consent_payload"
    if status_code == 408:
        return "timeout"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code <= 599:
        return "setu_server_error"
    return "setu_http_error"


def describe_setu_http_error(response: httpx.Response) -> Dict[str, Any]:
    details = safe_setu_error_details(response)
    return {
        "category": classify_setu_http_error(response),
        "http_status": response.status_code,
        "message": "; ".join(f"{key}: {value}" for key, value in details.items())[:1000],
    }


class AAProvider(ABC):
    source_label = "AA DATA"

    @abstractmethod
    async def create_consent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_consent_status(self, consent_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_data_session(self, consent_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_data(self, session_id: str) -> Any:
        raise NotImplementedError


class SetuConfigurationError(RuntimeError):
    pass


def build_consent_payload(payload: Dict[str, Any], redirect_url: str) -> Dict[str, Any]:
    """Build the current Setu AA Gateway consent request shape."""
    purpose_code = str(payload.get("purpose_code", "102"))
    purpose_text = str(payload.get("purpose", "Personal finance spending insights"))
    data_range_from = str(payload["data_range_from"])
    data_range_to = str(payload["data_range_to"])
    frequency_unit = str(payload.get("frequency_unit", "DAY")).upper()
    frequency_unit = {
        "HOURLY": "HOUR",
        "DAILY": "DAY",
        "MONTHLY": "MONTH",
        "YEARLY": "YEAR",
    }.get(frequency_unit, frequency_unit)
    return {
        "consentDuration": {
            "unit": str(payload.get("consent_duration_unit", "MONTH")),
            "value": int(payload.get("consent_duration_value", 4)),
        },
        "vua": str(payload["mobile_number"]),
        "dataRange": {"from": data_range_from, "to": data_range_to},
        "consentMode": str(payload.get("consent_mode", "STORE")),
        "fetchType": str(payload.get("fetch_type", "ONETIME")),
        "consentTypes": list(payload.get("consent_types", ["TRANSACTIONS"])),
        "fiTypes": list(payload.get("fi_types", ["DEPOSIT"])),
        "purpose": {
            "category": {
                "type": "string",
            },
            "code": purpose_code,
            "refUri": f"https://api.rebit.org.in/aa/purpose/{purpose_code}.xml",
            "text": purpose_text,
        },
        "dataLife": {
            "unit": str(payload.get("data_life_unit", "MONTH")),
            "value": int(payload.get("data_life_value", 1)),
        },
        "frequency": {
            "unit": frequency_unit,
            "value": int(payload.get("frequency_value", 1)),
        },
        "redirectUrl": redirect_url,
        "context": [
            {"key": "purposeCode", "value": purpose_code},
            {"key": "purposeDescription", "value": purpose_text},
        ],
    }


class SetuAAProvider(AAProvider):
    """Thin Setu AA adapter; financial payloads are returned only to the caller."""

    source_label = "SETU SANDBOX DATA"

    def __init__(self) -> None:
        self.base_url = settings.setu_base_url.rstrip("/")
        self.auth_base_url = settings.setu_auth_base_url.rstrip("/")
        self.client_id = settings.setu_client_id
        self.client_secret = settings.setu_client_secret
        self.product_instance_id = settings.setu_product_instance_id
        self.access_token = ""
        self.access_token_expires_at = 0.0
        if not all([self.base_url, self.auth_base_url, self.client_id, self.client_secret, self.product_instance_id]):
            raise SetuConfigurationError(
                "MOCK_MODE=false requires SETU_BASE_URL, SETU_CLIENT_ID, "
                "SETU_CLIENT_SECRET, and SETU_PRODUCT_INSTANCE_ID"
            )

    async def _headers(self) -> Dict[str, str]:
        if not self.access_token or time.monotonic() >= self.access_token_expires_at:
            auth_url = self.auth_base_url + "/v1/users/login"
            logger.info("Setu authentication request started url=%s", safe_setu_url(auth_url))
            async with httpx.AsyncClient(timeout=20) as client:
                try:
                    response = await client.post(auth_url, json={
                        "clientID": self.client_id,
                        "secret": self.client_secret,
                        "grant_type": "client_credentials",
                    }, headers={"client": "bridge"})
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    description = describe_setu_http_error(exc.response)
                    logger.error(
                        "Setu authentication failed url=%s category=%s http_status=%s details=%s",
                        safe_setu_url(auth_url),
                        description["category"],
                        description["http_status"],
                        description["message"],
                    )
                    raise
                except httpx.TimeoutException:
                    logger.error("Setu authentication timed out url=%s", safe_setu_url(auth_url))
                    raise
                except httpx.HTTPError as exc:
                    logger.error("Setu authentication network error url=%s error_type=%s", safe_setu_url(auth_url), type(exc).__name__)
                    raise
                token_payload = response.json()
                self.access_token = token_payload.get("access_token", "")
                expires_in = float(token_payload.get("expires_in", 300) or 300)
                self.access_token_expires_at = time.monotonic() + max(expires_in - 30, 30)
            if not self.access_token:
                logger.error("Setu authentication response did not contain an access token")
                raise SetuConfigurationError("Setu authentication did not return an access_token")
        return {
            "Authorization": "Bearer " + self.access_token,
            "Content-Type": "application/json",
            "x-product-instance-id": self.product_instance_id,
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        url = self.base_url + path
        request_body = kwargs.get("json")
        body_keys = sorted(request_body.keys()) if isinstance(request_body, dict) else []
        logger.info("Setu API request started method=%s url=%s body_keys=%s", method, safe_setu_url(url), body_keys)
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.request(method, url, headers=await self._headers(), **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                description = describe_setu_http_error(exc.response)
                logger.error(
                    "Setu API request failed method=%s url=%s category=%s http_status=%s details=%s",
                    method,
                    safe_setu_url(url),
                    description["category"],
                    description["http_status"],
                    description["message"],
                )
                raise
            except httpx.TimeoutException:
                logger.error("Setu API request timed out method=%s url=%s", method, safe_setu_url(url))
                raise
            except httpx.HTTPError as exc:
                logger.error("Setu API network error method=%s url=%s error_type=%s", method, safe_setu_url(url), type(exc).__name__)
                raise

    async def create_consent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "/v2/consents", json=payload)

    async def get_consent_status(self, consent_id: str) -> Dict[str, Any]:
        return await self._request("GET", "/v2/consents/" + consent_id)

    async def create_data_session(self, consent_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = dict(payload or {})
        body["consentId"] = consent_id
        return await self._request("POST", "/sessions", json=body)

    async def fetch_data(self, session_id: str) -> Any:
        return await self._request("GET", "/sessions/" + session_id)


def get_aa_provider() -> AAProvider:
    return MockAAProvider() if settings.mock_mode else SetuAAProvider()
