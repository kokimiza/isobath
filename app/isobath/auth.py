"""Supabase JWT verification (SEC-AUTH-02)."""

import hashlib
import uuid
from functools import lru_cache

import jwt
from fastapi import Request

from .config import get_settings
from .errors import api_error

ALLOWED_ALGORITHMS = ["ES256", "RS256"]  # asymmetric only: rejects "none" and HS*


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    s = get_settings()
    return jwt.PyJWKClient(f"{s.supabase_url}/auth/v1/.well-known/jwks.json", cache_keys=True)


def decode_token(token: str, key, issuer: str, audience: str) -> dict:
    claims = jwt.decode(
        token,
        key,
        algorithms=ALLOWED_ALGORITHMS,
        audience=audience,
        issuer=issuer,
        options={"require": ["exp", "iss", "aud", "sub"]},
    )
    uuid.UUID(claims["sub"])  # sub must be a Supabase user id
    return claims


def user_hash(sub: str) -> str:
    return hashlib.sha256((sub + get_settings().log_salt).encode()).hexdigest()[:16]


def current_claims(request: Request) -> dict:
    """FastAPI dependency: verified claims of the caller. user id comes only from `sub`."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise api_error(401, "unauthenticated")
    token = header[7:]
    s = get_settings()
    try:
        key = _jwks_client().get_signing_key_from_jwt(token).key
        claims = decode_token(token, key, f"{s.supabase_url}/auth/v1", s.jwt_audience)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise api_error(401, "invalid_token") from None
    request.state.user_hash = user_hash(claims["sub"])
    return claims
