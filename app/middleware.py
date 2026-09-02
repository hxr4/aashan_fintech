"""Request-path security: headers, transport, rate limits, and safe errors."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


# --- security headers ------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Defaults that assume the response may be rendered in a browser.

    The API serves JSON and a small local dashboard, so the content policy is
    deliberately tight: no plugins, no framing, no cross-origin embedding, and
    a referrer policy that never leaks a path to a third party.
    """

    def __init__(self, app, production: bool) -> None:
        super().__init__(app)
        self.production = production

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        if self.production:
            headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
        # Financial responses must never sit in a shared cache.
        if request.url.path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store, private")
        return response


# --- rate limiting ---------------------------------------------------------

# Sliding window per identity per bucket: (max_requests, window_seconds).
LIMITS: Dict[str, Tuple[int, int]] = {
    "auth": (20, 60),
    "ingest": (30, 60),
    "webhook": (120, 60),
    "default": (240, 60),
}
UNAUTHENTICATED_FACTOR = 0.25


def bucket_for(path: str) -> str:
    if path.startswith("/api/auth"):
        return "auth"
    if path.startswith("/api/ingest"):
        return "ingest"
    if path.startswith("/api/webhooks"):
        return "webhook"
    return "default"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """A sliding-window limiter held in process memory.

    Stated plainly because it matters operationally: this counts per process,
    so N workers allow N times the limit, and a restart forgets everything. It
    raises the cost of scripted abuse and protects a single-instance
    deployment. Anything multi-instance needs a shared store, and an edge
    layer remains the right place for volumetric and bot defence.
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)

    @staticmethod
    def _identity(request: Request) -> Tuple[str, bool]:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
            if token:
                # Hash rather than store: the bucket key must not be a credential.
                return "tok:" + hashlib.sha256(token.encode()).hexdigest()[:16], True
        client = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded and settings.trust_proxy_headers:
            client = forwarded.split(",")[0].strip()
        return "ip:" + client, False

    async def dispatch(self, request: Request, call_next: Callable):
        if not settings.rate_limit_enabled or request.url.path in {"/health", "/dev"}:
            return await call_next(request)

        identity, authenticated = self._identity(request)
        bucket = bucket_for(request.url.path)
        allowed, window = LIMITS[bucket]
        if not authenticated:
            allowed = max(5, int(allowed * UNAUTHENTICATED_FACTOR))

        now = time.monotonic()
        hits = self._hits[(identity, bucket)]
        while hits and now - hits[0] > window:
            hits.popleft()

        if len(hits) >= allowed:
            retry_after = int(window - (now - hits[0])) + 1
            logger.warning("rate limit hit bucket=%s authenticated=%s", bucket, authenticated)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Slow down."},
                headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"},
            )

        hits.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(allowed)
        response.headers["X-RateLimit-Remaining"] = str(max(0, allowed - len(hits)))
        return response


# --- safe errors -----------------------------------------------------------

class CorrelationMiddleware(BaseHTTPMiddleware):
    """Give every request an id so a user can quote it without us logging them."""

    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            # Never let a stack trace, a query, or a payload reach the client.
            logger.exception("unhandled error request_id=%s path=%s", request_id, request.url.path)
            return JSONResponse(
                status_code=500,
                content={"detail": "Something went wrong.", "request_id": request_id},
                headers={"X-Request-Id": request_id, "Cache-Control": "no-store"},
            )
        response.headers["X-Request-Id"] = request_id
        return response
