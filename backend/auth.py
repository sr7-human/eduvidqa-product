"""Supabase JWT verification for FastAPI."""
from __future__ import annotations

import os

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)

_jwks_client: PyJWKClient | None = None


def _get_jwt_secret() -> str:
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET must be set in .env")
    return secret


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        url = os.getenv("SUPABASE_URL")
        if not url:
            raise RuntimeError("SUPABASE_URL must be set in .env")
        _jwks_client = PyJWKClient(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json")
    return _jwks_client


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """Verify Supabase JWT. Supports both legacy HS256 and modern asymmetric (ES256/RS256) tokens."""
    if credentials is None:
        return None
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        if alg == "HS256":
            payload = jwt.decode(
                token,
                _get_jwt_secret(),
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[alg],
                audience="authenticated",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "JWT verification failed (alg=%s): %s",
            (jwt.get_unverified_header(token).get("alg") if token else "?"),
            exc,
        )
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


async def require_auth(token: dict | None = Depends(verify_token)) -> str:
    """Returns user_id (sub claim) or raises 401."""
    if token is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return token["sub"]


async def optional_auth(token: dict | None = Depends(verify_token)) -> str | None:
    """Returns user_id or None (for demo/unauthenticated access)."""
    return token.get("sub") if token else None


def _admin_emails() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


async def require_admin(token: dict | None = Depends(verify_token)) -> str:
    """Returns user_id if email is in ADMIN_EMAILS, else 403."""
    if token is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    email = (token.get("email") or "").lower()
    if not email or email not in _admin_emails():
        raise HTTPException(status_code=403, detail="Admin only")
    return token["sub"]


async def is_admin_email(token: dict | None = Depends(verify_token)) -> bool:
    """Non-blocking helper: returns True if the user is an admin."""
    if token is None:
        return False
    email = (token.get("email") or "").lower()
    return bool(email and email in _admin_emails())
