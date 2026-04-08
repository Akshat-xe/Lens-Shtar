from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import SupabaseUser, verify_supabase_jwt
from app.config import Settings, get_settings
from app import session_store

bearer_scheme = HTTPBearer(auto_error=False)


async def get_settings_dep() -> Settings:
    return get_settings()


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> SupabaseUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = verify_supabase_jwt(creds.credentials, settings)
    # Extend inactivity window on any authenticated request
    session_store.touch_user(user.user_id)
    return user


def require_session_api_key(user: Annotated[SupabaseUser, Depends(get_current_user)]) -> SupabaseUser:
    if not session_store.has_gemini_key(user.user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key required",
        )
    return user
