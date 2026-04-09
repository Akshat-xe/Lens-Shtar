"""
gemini_client.py — Production-grade Gemini REST client.

Model strategy (April 2026 free tier):
  Primary  : gemini-2.5-flash      (~10 RPM, ~250 RPD, best quality/speed)
  Fallback : gemini-2.5-flash-lite (~15 RPM, ~1000 RPD, lighter but reliable)

Retry strategy:
  - Exponential backoff WITH full jitter (Google's official recommendation).
  - Respects Retry-After header from Google when present.
  - Up to MAX_RETRIES attempts per call before falling back to next model.
  - Automatic model fallback: if primary 429s, retries entire call on fallback model.

NOTE: gemini-2.0-flash and gemini-2.0-flash-lite are deprecated as of April 2026.
"""
from __future__ import annotations

import asyncio
import base64
import json
import random
import re
from typing import Any

import httpx

from app.config import Settings

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.I)

# ── Model fallback chain ──────────────────────────────────────────────────────
# Primary model from settings, with automatic fallback to the more lenient one.
FALLBACK_MODEL = "gemini-2.5-flash-lite"

# ── Retry configuration ───────────────────────────────────────────────────────
MAX_RETRIES_PER_MODEL = 4        # attempts before giving up on a model
BASE_BACKOFF_SECONDS  = 4.0      # initial wait; doubles each retry
MAX_BACKOFF_SECONDS   = 60.0     # cap per retry
# Full jitter: actual wait = random(0, min(cap, base * 2^attempt))
# This is Google Cloud's recommended backoff strategy.


EXTRACTION_PROMPT = """You are a precise bank/credit-card statement parser. Read the attached PDF and extract ALL transactions.

Return ONLY valid JSON (no markdown) with exactly this shape:
{
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "amount": 123.45,
      "flow": "debit",
      "merchant_raw": "raw text from statement",
      "merchant_clean": "human readable merchant name",
      "category_suggestion": "Food & Dining | Housing | Transportation | Shopping | Subscriptions | Utilities | Entertainment | Health | Income | Transfers | EMIs | Other",
      "description": "short memo",
      "payment_method": "UPI | Card | NEFT | IMPS | Cash | Auto-debit | EMI | Other"
    }
  ]
}

Rules:
- amount is ALWAYS positive. Use flow: "credit" for money in, "debit" for money out.
- Infer payment_method from keywords (UPI, NEFT, POS, ATM, etc.). Use UPI when UPI appears.
- Clean merchant names (remove extra reference codes where obvious).
- If a field is unknown, still output best-effort values (use Other for category when unsure).
"""

SUMMARY_PROMPT_TEMPLATE = """You are a financial coach. Write a concise summary (max 120 words) for the user based ONLY on the aggregated facts below.
Do NOT invent numbers. Do NOT recalculate totals—treat the figures as authoritative.
Tone: professional, supportive, premium.

Facts (JSON):
{facts_json}
"""


def _parse_json_loose(text: str) -> dict[str, Any]:
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def _map_gemini_error(status_code: int, body: str) -> tuple[int, str]:
    """Parse Gemini error body and return (http_code, user_message)."""
    # Try to extract Google's own error message
    detail_msg = ""
    quota_type = ""
    try:
        err_json = json.loads(body)
        err = err_json.get("error", {})
        detail_msg = err.get("message", "")
        # Google includes quota violation details in error.details
        for detail in err.get("details", []):
            violations = detail.get("violations", [])
            for v in violations:
                quota_type = v.get("quotaId", "")
    except Exception:
        pass

    print(f"[gemini] HTTP {status_code} | quota={quota_type!r} | detail={detail_msg[:200]!r}")

    low = body.lower()
    if status_code in (401, 403) or "api key" in low or "permission" in low:
        return 401, (
            "Invalid Gemini API key or insufficient permissions. "
            "Check your key at https://aistudio.google.com/apikey"
        )
    if status_code == 429:
        hint = ""
        if "per_day" in low or "daily" in low or "rpd" in low:
            hint = " Your DAILY quota is exhausted — resets at midnight Pacific time (UTC-8). Use CSV upload to bypass Gemini entirely."
        elif "per_minute" in low or "rpm" in low or "rate" in low:
            hint = " Per-minute limit hit — the retry system will wait and retry automatically."
        return 429, f"Gemini rate limit exceeded.{hint}"
    if status_code in (500, 503):
        return 502, "Gemini service temporarily unavailable. Please retry in a moment."
    if status_code == 504:
        return 504, "Gemini timed out processing your file. Try a smaller/shorter statement."
    if status_code == 413 or "size" in low:
        return 413, "File or payload too large for Gemini. Try a smaller statement or export as CSV."
    return 502, f"Gemini request failed (HTTP {status_code}). Try again or use CSV/XLS export."


def _jitter_backoff(attempt: int) -> float:
    """
    Full-jitter exponential backoff — Google's recommended strategy.
    wait = random(0, min(MAX_BACKOFF, BASE * 2^attempt))
    """
    cap = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** attempt))
    return random.uniform(0, cap)


async def _gemini_post_with_retry(
    url_template: str,      # contains {model} placeholder
    api_key: str,
    body: dict[str, Any],
    primary_model: str,
    settings: Settings,
    operation: str = "request",
) -> tuple[httpx.Response, str]:
    """
    POST to Gemini with:
      1. Exponential backoff + jitter retries on 429/503.
      2. Automatic model fallback: primary → FALLBACK_MODEL on persistent 429.

    Returns (response, model_used).
    """
    timeout = settings.gemini_timeout_seconds

    models_to_try: list[str] = [primary_model]
    if primary_model != FALLBACK_MODEL:
        models_to_try.append(FALLBACK_MODEL)

    last_response: httpx.Response | None = None

    for model in models_to_try:
        url = url_template.format(model=model)
        print(f"[gemini] {operation}: using model={model}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(MAX_RETRIES_PER_MODEL + 1):
                try:
                    r = await client.post(url, params={"key": api_key}, json=body)
                except httpx.TimeoutException:
                    print(f"[gemini] {operation}: timeout on attempt {attempt+1}")
                    if attempt >= MAX_RETRIES_PER_MODEL:
                        raise GeminiHttpError(504, "Gemini timed out. Try a shorter statement.")
                    wait = _jitter_backoff(attempt)
                    await asyncio.sleep(wait)
                    continue

                if r.status_code == 200:
                    print(f"[gemini] {operation}: ✓ success with model={model}")
                    return r, model

                if r.status_code in (429, 503) and attempt < MAX_RETRIES_PER_MODEL:
                    # Respect Retry-After header if provided
                    retry_after_header = (
                        r.headers.get("retry-after")
                        or r.headers.get("x-ratelimit-reset-after")
                    )
                    if retry_after_header:
                        try:
                            wait = min(float(retry_after_header), MAX_BACKOFF_SECONDS)
                        except ValueError:
                            wait = _jitter_backoff(attempt)
                    else:
                        wait = _jitter_backoff(attempt)

                    print(
                        f"[gemini] {operation}: {r.status_code} on attempt {attempt+1}/{MAX_RETRIES_PER_MODEL+1} "
                        f"with {model}. Waiting {wait:.1f}s…"
                    )
                    await asyncio.sleep(wait)
                    continue

                # Non-retryable or retries exhausted
                last_response = r
                break
            else:
                # Loop completed without break — all retries failed with 429/503
                last_response = r  # type: ignore[possibly-undefined]

        # If we get here on a non-200 response, try next model
        if last_response is not None and last_response.status_code in (429, 503):
            print(
                f"[gemini] {operation}: all retries exhausted on {model}. "
                f"{'Falling back to ' + FALLBACK_MODEL if model != FALLBACK_MODEL else 'No more models.'}"
            )
            continue

        # Non-retryable error — don't try next model
        break

    # All models failed
    if last_response is not None:
        return last_response, primary_model

    raise GeminiHttpError(502, "Gemini request failed after all retries.")


async def extract_transactions_from_pdf(
    api_key: str,
    pdf_bytes: bytes,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Extract transactions from a PDF using Gemini vision."""
    if len(pdf_bytes) > settings.max_upload_bytes:
        raise ValueError("PDF exceeds configured upload limit")

    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    url_template = (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    body: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": EXTRACTION_PROMPT},
                    {"inline_data": {"mime_type": "application/pdf", "data": b64}},
                ],
            }
        ],
        "generation_config": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    }

    print(
        f"[gemini] extract_transactions_from_pdf: "
        f"PDF={len(pdf_bytes)//1024}kB, primary_model={settings.gemini_model}"
    )
    r, model_used = await _gemini_post_with_retry(
        url_template, api_key, body, settings.gemini_model, settings, "extract_transactions"
    )

    if r.status_code != 200:
        code, msg = _map_gemini_error(r.status_code, r.text)
        if r.status_code == 429:
            msg += (
                " TIP: Export your statement as CSV/XLS instead — "
                "those are parsed locally with zero Gemini quota."
            )
        raise GeminiHttpError(code, msg)

    try:
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = _parse_json_loose(text)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
        print(f"[gemini] extract_transactions: bad response shape. Body[:600]: {r.text[:600]}")
        raise GeminiHttpError(
            502,
            "Gemini returned an unexpected response format. "
            "Try exporting your statement as CSV or reduce statement length.",
        ) from e

    txs = parsed.get("transactions")
    if not isinstance(txs, list):
        raise GeminiHttpError(502, "Gemini JSON missing 'transactions' array.")

    out: list[dict[str, Any]] = [item for item in txs if isinstance(item, dict)]
    print(f"[gemini] extract_transactions: ✓ extracted {len(out)} transactions (model={model_used})")
    return out


async def generate_ai_summary(
    api_key: str,
    facts: dict[str, Any],
    settings: Settings,
) -> str:
    """Generate a financial narrative summary using Gemini."""
    facts_json = json.dumps(facts, ensure_ascii=False, default=str)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(facts_json=facts_json)
    url_template = (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generation_config": {"temperature": 0.35, "max_output_tokens": 512},
    }

    # Use a shorter timeout for summary (less critical than extraction)
    class _SummarySettings:
        """Proxy settings with reduced timeout for summary calls."""
        def __init__(self, s: Settings):
            self._s = s
            self.gemini_timeout_seconds = min(s.gemini_timeout_seconds, 60.0)
            self.gemini_model = s.gemini_model

        def __getattr__(self, name: str):
            return getattr(self._s, name)

    print(f"[gemini] generate_ai_summary: primary_model={settings.gemini_model}")
    r, model_used = await _gemini_post_with_retry(
        url_template, api_key, body, settings.gemini_model,
        _SummarySettings(settings),  # type: ignore[arg-type]
        "generate_ai_summary",
    )

    if r.status_code != 200:
        code, msg = _map_gemini_error(r.status_code, r.text)
        raise GeminiHttpError(r.status_code if r.status_code in (401, 403, 429) else 502, msg)

    try:
        data = r.json()
        return str(data["candidates"][0]["content"]["parts"][0]["text"]).strip()
    except (KeyError, IndexError, TypeError) as e:
        print(f"[gemini] generate_ai_summary: bad response. Body[:400]: {r.text[:400]}")
        raise GeminiHttpError(502, "Could not read Gemini summary response.") from e


class GeminiHttpError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)
