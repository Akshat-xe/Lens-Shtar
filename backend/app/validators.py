import re

from fastapi import HTTPException, status


_GEMINI_KEY_RE = re.compile(r"^[\w\-]{20,256}$")


def validate_gemini_api_key_format(key: str) -> str:
    """
    Basic validation only — no network calls, no persistence.
    Google AI (Gemini) keys are typically 'AIza…' strings; we allow a slightly wider safe set.
    """
    if not key or not isinstance(key, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="gemini_api_key is required",
        )
    cleaned = key.strip()
    if not cleaned.startswith("AIza"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid API key format",
        )
    if not _GEMINI_KEY_RE.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid API key format",
        )
    return cleaned
