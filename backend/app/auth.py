from dataclasses import dataclass

import jwt
from fastapi import HTTPException, status

from app.config import Settings


@dataclass(frozen=True)
class SupabaseUser:
    user_id: str


def verify_supabase_jwt(token: str, settings: Settings) -> SupabaseUser:
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: SUPABASE_JWT_SECRET is not set",
        )
    decode_kw: dict = {
        "algorithms": ["HS256"],
        "options": {"require": ["exp", "sub"]},
        "leeway": 10,
    }
    if settings.supabase_jwt_audience:
        decode_kw["audience"] = settings.supabase_jwt_audience
    else:
        decode_kw["options"] = {**decode_kw["options"], "verify_aud": False}

    try:
        payload = jwt.decode(token, settings.supabase_jwt_secret, **decode_kw)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )
    return SupabaseUser(user_id=sub)
