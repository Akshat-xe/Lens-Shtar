"""In-memory analysis results keyed by file_id (process lifetime only)."""

from __future__ import annotations

import threading
import time
from typing import Any

_store: dict[str, dict[str, Any]] = {}
_lock = threading.RLock()


def save_analysis(file_id: str, user_id: str, payload: dict[str, Any]) -> None:
    with _lock:
        _store[file_id] = {
            **payload,
            "_owner_user_id": user_id,
            "_created_at": time.time(),
        }


def get_analysis(file_id: str) -> dict[str, Any] | None:
    with _lock:
        row = _store.get(file_id)
        if not row:
            return None
        return dict(row)


def get_for_user(file_id: str, user_id: str) -> dict[str, Any] | None:
    with _lock:
        row = _store.get(file_id)
        if not row or row.get("_owner_user_id") != user_id:
            return None
        out = {k: v for k, v in row.items() if not k.startswith("_")}
        out["file_id"] = file_id
        return out


def owner_user_id(file_id: str) -> str | None:
    with _lock:
        row = _store.get(file_id)
        if not row:
            return None
        uid = row.get("_owner_user_id")
        return uid if isinstance(uid, str) else None
