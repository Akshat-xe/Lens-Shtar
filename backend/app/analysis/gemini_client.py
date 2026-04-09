"""
gemini_client.py — Deep Financial Analyst Gemini client.

Extraction prompt is an expert-level financial analyst + behavioral economist prompt
that returns structured JSON across 6 categories:
  1. Profile & Verification
  2. Income & Cash Inflow Profiling
  3. Expense Categorization & Outflow Analytics
  4. Debt, Liabilities & Stress Indicators
  5. Savings, Investments & Insurance Health
  6. Behavioral & Vendor Insights

Model strategy (April 2026 free tier):
  Primary  : gemini-2.5-flash      (~10 RPM, ~250 RPD)
  Fallback : gemini-2.5-flash-lite (~15 RPM, ~1000 RPD)
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

FALLBACK_MODEL = "gemini-2.5-flash-lite"
MAX_RETRIES_PER_MODEL = 4
BASE_BACKOFF_SECONDS  = 4.0
MAX_BACKOFF_SECONDS   = 60.0


# ── Deep Extraction Prompt ────────────────────────────────────────────────────
EXTRACTION_PROMPT = """You are an expert Financial Analyst and Behavioral Economist.
Analyze the provided bank/credit-card statement PDF thoroughly.

Return ONLY a single valid JSON object (no markdown, no explanation) with exactly this structure:

{
  "profile": {
    "account_holder_name": "string or null",
    "account_number_masked": "string or null (last 4 digits only if visible)",
    "bank_name": "string or null",
    "account_type": "Savings | Current | Credit Card | null",
    "branch": "string or null",
    "ifsc": "string or null",
    "statement_from": "YYYY-MM-DD or null",
    "statement_to": "YYYY-MM-DD or null"
  },
  "income_profile": {
    "primary_source": "string describing main income source",
    "primary_frequency": "Monthly | Bi-weekly | Weekly | Irregular | null",
    "income_consistency": "Fixed | Variable | Freelance | Mixed",
    "secondary_sources": ["list of secondary income types identified"]
  },
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "amount": 123.45,
      "flow": "debit | credit",
      "merchant_raw": "exact text from statement",
      "merchant_clean": "readable merchant name",
      "category": "Food & Dining | Housing | Transportation | Shopping | Subscriptions | Utilities | Entertainment | Health & Wellness | Income | Transfers | EMIs | Insurance | Investments | Education | Cash & ATM | Other",
      "sub_category": "more specific label e.g. Fuel, Groceries, OTT, SIP, etc.",
      "description": "short memo",
      "payment_method": "UPI | Card | NEFT | IMPS | RTGS | Cash | Auto-debit | EMI | Cheque | Other",
      "is_emi": false,
      "is_recurring": false,
      "is_investment": false,
      "is_insurance": false,
      "stress_flag": false
    }
  ],
  "stress_indicators": {
    "overdraft_events": 0,
    "bounced_transactions": 0,
    "late_payment_fees": 0,
    "micro_borrowing_count": 0,
    "notes": "any notable stress patterns observed"
  },
  "behavioral_insights": {
    "post_payday_splurge": true,
    "cash_reliance_pct": 12.5,
    "top_vendors": ["vendor1", "vendor2", "vendor3"],
    "spending_pattern": "description of spending timing and habits"
  }
}

Extraction rules:
- amount is ALWAYS a positive number. Use flow: "credit" for money IN, "debit" for money OUT.
- Infer payment_method from transaction narration keywords (UPI→UPI, POS/CARD→Card, NACH/ECS→Auto-debit, ATM→Cash).
- Set is_emi=true for EMI/NACH/loan repayments.
- Set is_recurring=true for transactions appearing regularly (same merchant, similar amount, multiple months).
- Set is_investment=true for SIP, mutual fund, RD, FD, stock purchases.
- Set is_insurance=true for LIC, health/vehicle/term insurance premiums.
- Set stress_flag=true for overdraft, bounced, penalty, late fee entries.
- Extract ALL transactions — do not skip any. Even transfers and internal credits.
- post_payday_splurge=true if high spending within 7 days post largest credit.
- cash_reliance_pct = (ATM withdrawals / total debits) * 100.
- If a field is truly unknown, use null — never invent data.
"""

SUMMARY_PROMPT_TEMPLATE = """You are a Senior Financial Coach at a premium wealth management firm.
Write a professional yet warm narrative summary (max 150 words) for the client based ONLY on verified facts below.

Do NOT invent numbers. Use the exact figures. Be specific, actionable, and India-aware (₹, INR context).
Structure: 2 sentences on income health, 2 on expense/savings, 1 on top risk, 1 motivating recommendation.

Verified Financial Facts:
{facts_json}
"""


def _parse_json_loose(text: str) -> dict[str, Any]:
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def _map_gemini_error(status_code: int, body: str) -> tuple[int, str]:
    detail_msg = ""
    try:
        err_json = json.loads(body)
        detail_msg = err_json.get("error", {}).get("message", "")
    except Exception:
        pass
    print(f"[gemini] HTTP {status_code} | detail={detail_msg[:200]!r}")
    low = body.lower()
    if status_code in (401, 403) or "api key" in low or "permission" in low:
        return 401, "Invalid Gemini API key or insufficient permissions. Check your key at https://aistudio.google.com/apikey"
    if status_code == 429:
        hint = " (daily quota exhausted — resets at midnight Pacific. Use CSV upload to bypass Gemini entirely.)" if "per_day" in low or "daily" in low else " (per-minute limit — retry system will backoff and retry automatically.)"
        return 429, f"Gemini rate limit exceeded.{hint}"
    if status_code in (500, 503):
        return 502, "Gemini service temporarily unavailable. Please retry."
    if status_code == 504:
        return 504, "Gemini timed out. Try a shorter/smaller statement."
    if status_code == 413 or "size" in low:
        return 413, "File too large for Gemini. Try a smaller statement or export as CSV."
    return 502, f"Gemini request failed (HTTP {status_code}). Try CSV/XLS export as alternative."


def _jitter_backoff(attempt: int) -> float:
    cap = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** attempt))
    return random.uniform(0, cap)


async def _gemini_post_with_retry(
    url_template: str,
    api_key: str,
    body: dict[str, Any],
    primary_model: str,
    settings: Settings,
    operation: str = "request",
) -> tuple[httpx.Response, str]:
    timeout = settings.gemini_timeout_seconds
    models_to_try = [primary_model]
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
                    print(f"[gemini] {operation}: timeout attempt {attempt+1}")
                    if attempt >= MAX_RETRIES_PER_MODEL:
                        raise GeminiHttpError(504, "Gemini timed out. Try a shorter statement.")
                    await asyncio.sleep(_jitter_backoff(attempt))
                    continue
                if r.status_code == 200:
                    print(f"[gemini] {operation}: ✓ success model={model}")
                    return r, model
                if r.status_code in (429, 503) and attempt < MAX_RETRIES_PER_MODEL:
                    ra = r.headers.get("retry-after") or r.headers.get("x-ratelimit-reset-after")
                    wait = min(float(ra), MAX_BACKOFF_SECONDS) if ra else _jitter_backoff(attempt)
                    print(f"[gemini] {operation}: {r.status_code} attempt {attempt+1}, waiting {wait:.1f}s…")
                    await asyncio.sleep(wait)
                    continue
                last_response = r
                break
            else:
                last_response = r  # type: ignore[possibly-undefined]
        if last_response is not None and last_response.status_code in (429, 503):
            print(f"[gemini] {operation}: retries exhausted on {model}, {'trying fallback' if model != FALLBACK_MODEL else 'no more models'}")
            continue
        break
    if last_response is not None:
        return last_response, primary_model
    raise GeminiHttpError(502, "Gemini request failed after all retries.")


async def extract_transactions_from_pdf(
    api_key: str,
    pdf_bytes: bytes,
    settings: Settings,
) -> dict[str, Any]:
    """
    Returns a rich dict with keys:
      transactions, profile, income_profile, stress_indicators, behavioral_insights
    """
    if len(pdf_bytes) > settings.max_upload_bytes:
        raise ValueError("PDF exceeds configured upload limit")
    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    url_template = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body: dict[str, Any] = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": EXTRACTION_PROMPT},
                {"inline_data": {"mime_type": "application/pdf", "data": b64}},
            ],
        }],
        "generation_config": {
            "temperature": 0.05,
            "response_mime_type": "application/json",
        },
    }
    print(f"[gemini] extract_transactions_from_pdf: PDF={len(pdf_bytes)//1024}kB, model={settings.gemini_model}")
    r, model_used = await _gemini_post_with_retry(
        url_template, api_key, body, settings.gemini_model, settings, "extract_transactions"
    )
    if r.status_code != 200:
        code, msg = _map_gemini_error(r.status_code, r.text)
        if r.status_code == 429:
            msg += " TIP: Export statement as CSV/XLS — those are processed locally with zero Gemini quota."
        raise GeminiHttpError(code, msg)
    try:
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = _parse_json_loose(text)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
        print(f"[gemini] extract: bad response shape. Body[:600]: {r.text[:600]}")
        raise GeminiHttpError(502, "Gemini returned unexpected format. Try CSV export or reduce statement length.") from e
    txs = parsed.get("transactions")
    if not isinstance(txs, list):
        raise GeminiHttpError(502, "Gemini JSON missing 'transactions' array.")
    out = [item for item in txs if isinstance(item, dict)]
    print(f"[gemini] extract: ✓ {len(out)} transactions (model={model_used})")
    # Return full rich payload
    return {
        "transactions": out,
        "profile": parsed.get("profile") or {},
        "income_profile": parsed.get("income_profile") or {},
        "stress_indicators": parsed.get("stress_indicators") or {},
        "behavioral_insights": parsed.get("behavioral_insights") or {},
    }


async def generate_ai_summary(
    api_key: str,
    facts: dict[str, Any],
    settings: Settings,
) -> str:
    facts_json = json.dumps(facts, ensure_ascii=False, default=str)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(facts_json=facts_json)
    url_template = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generation_config": {"temperature": 0.4, "max_output_tokens": 600},
    }

    class _ReducedTimeout:
        def __init__(self, s: Settings):
            self._s = s
            self.gemini_timeout_seconds = min(s.gemini_timeout_seconds, 60.0)
            self.gemini_model = s.gemini_model
        def __getattr__(self, name: str):
            return getattr(self._s, name)

    print(f"[gemini] generate_ai_summary: model={settings.gemini_model}")
    r, _ = await _gemini_post_with_retry(
        url_template, api_key, body, settings.gemini_model,
        _ReducedTimeout(settings),  # type: ignore[arg-type]
        "generate_ai_summary",
    )
    if r.status_code != 200:
        code, msg = _map_gemini_error(r.status_code, r.text)
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
