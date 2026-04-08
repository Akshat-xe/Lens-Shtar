import threading
import time
from typing import Any

from app.config import get_settings

# In-memory only. Cleared on process restart. Never persisted.
# session_store[user_id] = {
#   "gemini_api_key": str | None,
#   "last_active": float (unix time),
#   "last_active_mono": float (monotonic, for inactivity deltas),
# }
_session_store: dict[str, dict[str, Any]] = {}
_lock = threading.RLock()


def _now_mono() -> float:
    return time.monotonic()


def _now_wall() -> float:
    return time.time()


def _expire_if_stale_locked(user_id: str) -> None:
    s = _session_store.get(user_id)
    if not s:
        return
    settings = get_settings()
    mono = s.get("last_active_mono")
    if mono is None:
        return
    if _now_mono() - float(mono) > settings.session_inactivity_seconds:
        _session_store.pop(user_id, None)


def touch_user(user_id: str) -> dict[str, Any]:
    """Return session row for user_id, refreshing activity; expire stale sessions."""
    with _lock:
        _expire_if_stale_locked(user_id)
        if user_id not in _session_store:
            _session_store[user_id] = {
                "gemini_api_key": None,
                "last_active": _now_wall(),
                "last_active_mono": _now_mono(),
            }
        row = _session_store[user_id]
        row["last_active"] = _now_wall()
        row["last_active_mono"] = _now_mono()
        return row


def set_gemini_key(user_id: str, api_key: str) -> None:
    with _lock:
        _expire_if_stale_locked(user_id)
        row = _session_store.setdefault(
            user_id,
            {
                "gemini_api_key": None,
                "last_active": _now_wall(),
                "last_active_mono": _now_mono(),
            },
        )
        row["gemini_api_key"] = api_key
        row["last_active"] = _now_wall()
        row["last_active_mono"] = _now_mono()


def clear_gemini_key(user_id: str) -> None:
    with _lock:
        row = _session_store.get(user_id)
        if not row:
            return
        row["gemini_api_key"] = None
        row["last_active"] = _now_wall()
        row["last_active_mono"] = _now_mono()


def has_gemini_key(user_id: str) -> bool:
    with _lock:
        _expire_if_stale_locked(user_id)
        row = _session_store.get(user_id)
        if not row:
            return False
        key = row.get("gemini_api_key")
        return bool(key and isinstance(key, str))


def get_gemini_key(user_id: str) -> str | None:
    """Return the user's Gemini API key from memory only. Never log this value."""
    with _lock:
        _expire_if_stale_locked(user_id)
        row = _session_store.get(user_id)
        if not row:
            return None
        key = row.get("gemini_api_key")
        if not key or not isinstance(key, str):
            return None
        return key
