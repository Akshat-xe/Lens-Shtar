"""
auth.py — Supabase JWT verification via JWKS (ES256 + HS256 supported).

Supabase now signs tokens with ES256 (asymmetric ECDSA). We fetch their
public JWKS endpoint once, cache the client, and use it to verify every token.
The old SUPABASE_JWT_SECRET env var is kept as a HS256 fallback for legacy
project setups, but is NOT required for ES256 projects.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

import jwt
from fastapi import HTTPException, status

from app.config import Settings


@dataclass(frozen=True)
class SupabaseUser:
    user_id: str


@functools.lru_cache(maxsize=1)
def _get_jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    """Cached JWKS client — fetched once from Supabase's public endpoint."""
    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    print(f"[auth] Fetching JWKS from: {jwks_url}")
    return jwt.PyJWKClient(jwks_url, cache_keys=True)


def verify_supabase_jwt(token: str, settings: Settings) -> SupabaseUser:
    """
    Verify a Supabase-issued JWT.

    Strategy:
      1. Try JWKS-based verification (ES256, RS256 — asymmetric keys from Supabase).
         This is the correct method for all modern Supabase projects.
      2. Fallback to HS256 with SUPABASE_JWT_SECRET for legacy projects that
         have not migrated to asymmetric signing.
    """
    decode_opts = {
        "options": {
            "require": ["exp", "sub"],
        },
        "leeway": 10,
    }

    # Set audience only if configured
    if settings.supabase_jwt_audience:
        decode_opts["audience"] = settings.supabase_jwt_audience
    else:
        decode_opts["options"]["verify_aud"] = False  # type: ignore[index]

    # ── Strategy 1: JWKS (ES256 / RS256 — modern Supabase) ──────────────────
    try:
        jwks_client = _get_jwks_client(settings.supabase_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            **decode_opts,
        )
        sub = payload.get("sub")
        if not sub or not isinstance(sub, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        print(f"[auth] ✓ JWKS verification succeeded for sub={sub}")
        return SupabaseUser(user_id=sub)

    except HTTPException:
        raise
    except jwt.ExpiredSignatureError as exc:
        print(f"[auth] Token expired: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        print(f"[auth] JWKS verification failed: {exc} — trying HS256 fallback")
        # Fall through to HS256 fallback below

    # ── Strategy 2: HS256 fallback (legacy Supabase with JWT secret) ─────────
    if settings.supabase_jwt_secret:
        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                **decode_opts,
            )
            sub = payload.get("sub")
            if not sub or not isinstance(sub, str):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing subject",
                )
            print(f"[auth] ✓ HS256 fallback verification succeeded for sub={sub}")
            return SupabaseUser(user_id=sub)
        except jwt.ExpiredSignatureError as exc:
            print(f"[auth] HS256 fallback: Token expired: {exc}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            ) from exc
        except jwt.InvalidTokenError as exc:
            print(f"[auth] HS256 fallback also failed: {exc}")
            # Fall through to final reject

    # Both strategies failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token: signature verification failed",
    )
