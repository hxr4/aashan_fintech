"""Supabase identity validation and reusable FastAPI ownership dependency.

Authentication is opt-in for local/demo mode so the existing SQLite test and
mock workflows remain usable. Production environments default to required
authentication. A user ID is never accepted from request JSON.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings


LOCAL_USER_ID = "00000000-0000-0000-0000-000000000001"
_bearer = HTTPBearer(auto_error=False)


class AuthenticationConfigurationError(RuntimeError):
    pass


class InvalidAccessToken(ValueError):
    pass


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: Optional[str] = None
    claims: Optional[Dict[str, Any]] = None
    is_local: bool = False


def _issuer() -> str:
    return settings.supabase_jwt_issuer or (
        f"{settings.supabase_url}/auth/v1" if settings.supabase_url else ""
    )


def validate_supabase_access_token(token: str) -> AuthenticatedUser:
    """Validate a Supabase JWT using PyJWT and return only trusted identity data.

    PyJWT[crypto] is an optional runtime dependency for local SQLite/demo use,
    but is required whenever AUTH_REQUIRED=true or a bearer token is supplied.
    """
    issuer = _issuer()
    if not issuer:
        raise AuthenticationConfigurationError(
            "SUPABASE_URL or SUPABASE_JWT_ISSUER must be configured for issuer validation"
        )

    try:
        import jwt
    except ImportError as exc:  # pragma: no cover - exercised in deployment
        raise AuthenticationConfigurationError(
            "PyJWT[crypto] is required for Supabase token validation"
        ) from exc

    if not settings.supabase_url and not settings.supabase_jwt_secret:
        raise AuthenticationConfigurationError(
            "SUPABASE_URL or SUPABASE_JWT_SECRET must be configured"
        )

    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm == "HS256":
            if not settings.supabase_jwt_secret:
                raise AuthenticationConfigurationError(
                    "SUPABASE_JWT_SECRET is required for HS256 token validation"
                )
            key = settings.supabase_jwt_secret
        elif algorithm == "RS256":
            if not settings.supabase_url:
                raise AuthenticationConfigurationError(
                    "SUPABASE_URL is required for RS256 JWKS validation"
                )
            jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
            key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(token).key
        else:
            raise InvalidAccessToken("Unsupported JWT signing algorithm")

        claims = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            audience=settings.supabase_jwt_audience,
            issuer=issuer,
            options={"require": ["sub", "exp"]},
        )
    except AuthenticationConfigurationError:
        raise
    except Exception as exc:
        raise InvalidAccessToken("Invalid or expired access token") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidAccessToken("Access token has no subject")
    return AuthenticatedUser(
        user_id=subject,
        email=claims.get("email") if isinstance(claims.get("email"), str) else None,
        claims=claims,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> AuthenticatedUser:
    """Return the authenticated owner, or the local demo owner in dev mode."""
    if credentials is None:
        if settings.auth_required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthenticatedUser(user_id=LOCAL_USER_ID, is_local=True)

    try:
        return validate_supabase_access_token(credentials.credentials)
    except AuthenticationConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidAccessToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_supabase_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> AuthenticatedUser:
    """Strict dependency for endpoints that must never run as local demo user."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_current_user(credentials)
