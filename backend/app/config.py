import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _env_bool(key: str, default: bool) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str
    supabase_jwt_audience: str
    cors_origins: str
    session_inactivity_seconds: int
    video_placeholder_enabled: bool
    max_upload_bytes: int
    gemini_model: str
    gemini_timeout_seconds: float
    gemini_ai_summary_enabled: bool

    @property
    def cors_origin_list(self) -> list[str]:
        raw = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return raw or ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    inactive = int(os.getenv("SESSION_INACTIVITY_SECONDS", "2700"))
    inactive = max(60, min(inactive, 86400))
    max_mb = float(os.getenv("MAX_UPLOAD_MB", "12"))
    max_upload = int(max(1, min(max_mb, 30)) * 1024 * 1024)
    gemini_timeout = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))
    gemini_timeout = max(30.0, min(gemini_timeout, 300.0))
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", "").strip(),
        supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET", "").strip(),
        supabase_jwt_audience=os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated").strip()
        or "authenticated",
        cors_origins=os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).strip(),
        session_inactivity_seconds=inactive,
        video_placeholder_enabled=_env_bool("VIDEO_PLACEHOLDER_ENABLED", True),
        max_upload_bytes=max_upload,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
        or "gemini-2.0-flash",
        gemini_timeout_seconds=gemini_timeout,
        gemini_ai_summary_enabled=_env_bool("GEMINI_AI_SUMMARY_ENABLED", True),
    )
