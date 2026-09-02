from typing import Any, Dict, Optional

import requests


DEFAULT_API_URL = "http://localhost:8000"


class APIClientError(RuntimeError):
    """Raised when the FastAPI dashboard API cannot be reached or responds with an error."""


def fetch_api(endpoint: str, base_url: str = DEFAULT_API_URL, timeout: float = 6.0) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise APIClientError("FastAPI returned an unexpected response for " + endpoint)
        return payload
    except requests.RequestException as exc:
        raise APIClientError("FastAPI is unavailable at %s" % base_url) from exc
    except ValueError as exc:
        raise APIClientError("FastAPI returned invalid JSON for " + endpoint) from exc


def post_api(endpoint: str, base_url: str = DEFAULT_API_URL, json: Optional[Dict[str, Any]] = None,
             files: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
    try:
        response = requests.post(url, json=json, files=files, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise APIClientError("FastAPI returned an unexpected response for " + endpoint)
        return payload
    except requests.RequestException as exc:
        raise APIClientError("FastAPI request failed for " + endpoint) from exc
    except ValueError as exc:
        raise APIClientError("FastAPI returned invalid JSON for " + endpoint) from exc


def fetch_summary(base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    return fetch_api("/api/dashboard/summary", base_url)


def fetch_categories(base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    return fetch_api("/api/dashboard/categories", base_url)


def fetch_monthly(base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    return fetch_api("/api/dashboard/monthly", base_url)


def fetch_patterns(base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    return fetch_api("/api/dashboard/patterns", base_url)


def fetch_anomalies(base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    return fetch_api("/api/dashboard/anomalies", base_url)


def fetch_privacy(base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    return fetch_api("/api/dashboard/privacy", base_url)


def fetch_budgets(base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    return fetch_api("/api/budgets/status", base_url)


def upload_csv(file_bytes: bytes, filename: str, base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    return post_api("/api/ingest/csv", base_url, files={"file": (filename, file_bytes, "text/csv")})


def create_mock_consent(base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    """Create a prototype AA consent through FastAPI; no AA logic lives in Streamlit."""
    return post_api("/api/aa/mock/consent", base_url, json={})


def create_consent(base_url: str = DEFAULT_API_URL, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return post_api("/api/aa/consent", base_url, json=payload or {})


def fetch_consent_status(consent_id: str, base_url: str = DEFAULT_API_URL) -> Dict[str, Any]:
    return fetch_api("/api/aa/consent/" + consent_id, base_url)
