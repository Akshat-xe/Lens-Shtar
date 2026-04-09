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
    unverified_header = jwt.get_unverified_header(token)
    alg = unverified_header.get("alg", "HS256")
    print(f"Token header alg is: {alg}")

    decode_kw: dict = {
        "algorithms": ["HS256", alg],
        "options": {"require": ["exp", "sub"]},
        "leeway": 10,
    }
    if settings.supabase_jwt_audience:
        decode_kw["audience"] = settings.supabase_jwt_audience
    else:
        decode_kw["options"] = {**decode_kw["options"], "verify_aud": False}

    try:
        payload = jwt.decode(token, settings.supabase_jwt_secret, **decode_kw)
    except jwt.InvalidSignatureError:
        # Fallback to base64 decoded secret if the plain string fails.
        import base64
        try:
            decoded_secret = base64.b64decode(settings.supabase_jwt_secret)
            payload = jwt.decode(token, decoded_secret, **decode_kw)
        except Exception as fallback_exc:
            print(f"Fallback base64 decode failed: {str(fallback_exc)}")
            raise jwt.InvalidSignatureError("Signature verification failed with both plain and base64 secret") from fallback_exc
    except jwt.ExpiredSignatureError as exc:
        print(f"JWT ExpiredSignatureError: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token expired: {str(exc)}",
        ) from exc
    except jwt.InvalidTokenError as exc:
        print(f"JWT InvalidTokenError: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(exc)}",
        ) from exc
    except Exception as exc:
        print(f"JWT Unknown Error: {str(exc)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unknown error: {str(exc)}",
        ) from exc

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )
    return SupabaseUser(user_id=sub)
