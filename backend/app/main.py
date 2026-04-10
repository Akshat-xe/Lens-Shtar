from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import session_store
from app.analysis.gemini_client import GeminiHttpError
from app.analysis.pipeline import (
    BadInputError,
    FileTooLargeError,
    MissingApiKeyError,
    PipelineError,
    UnsupportedFileError,
    run_upload_pipeline,
)
from app.analysis.store import get_for_user
from app.auth import SupabaseUser
from app.config import Settings, get_settings
from app.deps import get_current_user, get_settings_dep, require_session_api_key
from app.validators import validate_gemini_api_key_format


def _create_app() -> FastAPI:
    application = FastAPI(title="Lens Shtar API", version="0.1.0")
    settings = get_settings()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    return application


app = _create_app()


class SetApiKeyBody(BaseModel):
    gemini_api_key: str = Field(..., min_length=1)


class SettingsStatusResponse(BaseModel):
    has_api_key: bool
    video_placeholder_enabled: bool


@app.get("/")
def root():
    return {"status": "ok", "service": "Lens Shtar API", "version": "0.1.0"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/settings/set-api-key")
def set_api_key(
    body: SetApiKeyBody,
    user: Annotated[SupabaseUser, Depends(get_current_user)],
):
    key = validate_gemini_api_key_format(body.gemini_api_key)
    session_store.set_gemini_key(user.user_id, key)
    return {"ok": True}


@app.get("/api/settings/status", response_model=SettingsStatusResponse)
def settings_status(
    user: Annotated[SupabaseUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
):
    return SettingsStatusResponse(
        has_api_key=session_store.has_gemini_key(user.user_id),
        video_placeholder_enabled=settings.video_placeholder_enabled,
    )


@app.post("/api/settings/clear-api-key")
def clear_api_key(user: Annotated[SupabaseUser, Depends(get_current_user)]):
    session_store.clear_gemini_key(user.user_id)
    return {"ok": True}


@app.post("/api/upload")
async def upload(
    user: Annotated[SupabaseUser, Depends(require_session_api_key)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    file: UploadFile = File(...),
    include_ai_summary: bool = Query(True, description="Optional second Gemini call for narrative only."),
):
    """
    Analyze an uploaded statement (PDF via user Gemini key; CSV/XLS/XLSX parsed locally).
    """
    content = await file.read()
    try:
        return await run_upload_pipeline(
            user_id=user.user_id,
            filename=file.filename or "",
            content=content,
            content_type=file.content_type,
            settings=settings,
            include_ai_summary=include_ai_summary,
        )
    except GeminiHttpError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except MissingApiKeyError as e:
        raise HTTPException(status_code=e.http_status(), detail=str(e)) from e
    except FileTooLargeError as e:
        raise HTTPException(status_code=e.http_status(), detail=str(e)) from e
    except UnsupportedFileError as e:
        raise HTTPException(status_code=e.http_status(), detail=str(e)) from e
    except BadInputError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except PipelineError as e:
        raise HTTPException(status_code=e.http_status(), detail=str(e)) from e


@app.get("/api/dashboard/{file_id}")
def dashboard(
    file_id: str,
    user: Annotated[SupabaseUser, Depends(get_current_user)],
):
    """
    Full dashboard payload for a completed upload. Scoped to the authenticated user.
    """
    data = get_for_user(file_id, user.user_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found for this id, or you do not have access.",
        )
    return data
