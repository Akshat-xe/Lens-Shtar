from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.config import Settings

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.I)

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
- amount is ALWAYS positive. Use flow: \"credit\" for money in, \"debit\" for money out.
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
    low = body.lower()
    if status_code in (401, 403) or "api key" in low or "permission" in low or "invalid" in low:
        return 401, "Invalid Gemini API key or insufficient permissions for this model."
    if status_code == 429:
        return 429, "Gemini rate limit exceeded. Try again in a few minutes."
    if status_code == 413 or "size" in low:
        return 413, "File or payload too large for Gemini. Try a smaller statement export."
    return 502, "Gemini request failed. Try again later or use CSV/XLS export if available."


async def extract_transactions_from_pdf(
    api_key: str,
    pdf_bytes: bytes,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Call Gemini with the user's API key only (REST)."""
    if len(pdf_bytes) > settings.max_upload_bytes:
        raise ValueError("PDF exceeds configured upload limit")

    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    body: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": EXTRACTION_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": b64,
                        }
                    },
                ],
            }
        ],
        "generation_config": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=settings.gemini_timeout_seconds) as client:
        r = await client.post(url, params={"key": api_key}, json=body)

    if r.status_code != 200:
        code, msg = _map_gemini_error(r.status_code, r.text)
        raise GeminiHttpError(code, msg)

    try:
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = _parse_json_loose(text)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
        raise GeminiHttpError(
            502,
            "Gemini returned an unexpected response. Try exporting CSV or reduce statement length.",
        ) from e

    txs = parsed.get("transactions")
    if not isinstance(txs, list):
        raise GeminiHttpError(502, "Gemini JSON missing transactions array.")
    out: list[dict[str, Any]] = []
    for item in txs:
        if isinstance(item, dict):
            out.append(item)
    return out


async def generate_ai_summary(
    api_key: str,
    facts: dict[str, Any],
    settings: Settings,
) -> str:
    facts_json = json.dumps(facts, ensure_ascii=False, default=str)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(facts_json=facts_json)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generation_config": {"temperature": 0.35, "max_output_tokens": 512},
    }
    async with httpx.AsyncClient(timeout=min(settings.gemini_timeout_seconds, 90.0)) as client:
        r = await client.post(url, params={"key": api_key}, json=body)
    if r.status_code != 200:
        _, msg = _map_gemini_error(r.status_code, r.text)
        raise GeminiHttpError(r.status_code if r.status_code in (401, 403, 429) else 502, msg)
    try:
        data = r.json()
        return str(data["candidates"][0]["content"]["parts"][0]["text"]).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise GeminiHttpError(502, "Could not read Gemini summary response.") from e


class GeminiHttpError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)
