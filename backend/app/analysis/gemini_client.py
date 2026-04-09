"""
gemini_client.py — Bank-grade financial extraction with currency intelligence,
reconciliation data, and 12-point accuracy layer.
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

# ── Extraction Prompt (bank-grade accuracy, 12 reliability layers) ────────────
EXTRACTION_PROMPT = """You are a senior bank reconciliation analyst and forensic accountant.
Read the attached bank/credit-card statement PDF with maximum precision.

Return ONLY one valid JSON object — no markdown, no explanations, no truncation.

{
  "currency": {
    "code": "INR",
    "symbol": "₹",
    "locale": "en-IN",
    "detected_from": "statement_header | symbol | bank_name | inferred"
  },
  "balances": {
    "opening_balance": null,
    "closing_balance": null,
    "statement_total_credit": null,
    "statement_total_debit": null
  },
  "profile": {
    "account_holder_name": null,
    "account_number_masked": null,
    "bank_name": null,
    "account_type": "Savings | Current | Credit Card | null",
    "branch": null,
    "ifsc": null,
    "statement_from": null,
    "statement_to": null
  },
  "income_profile": {
    "primary_source": null,
    "primary_frequency": "Monthly | Bi-weekly | Weekly | Irregular | null",
    "income_consistency": "Fixed | Variable | Freelance | Mixed",
    "secondary_sources": []
  },
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "amount": 0.00,
      "flow": "debit | credit",
      "balance_after": null,
      "merchant_raw": "verbatim text from statement",
      "merchant_clean": "human-readable name",
      "category": "Food & Dining | Housing | Transportation | Shopping | Subscriptions | Utilities | Entertainment | Health & Wellness | Income | Transfers | EMIs | Insurance | Investments | Education | Cash & ATM | Other",
      "sub_category": "Fuel | Groceries | OTT | SIP | Rent | Salary | Dining | Pharmacy | etc.",
      "description": "30-word memo",
      "payment_method": "UPI | Card | NEFT | IMPS | RTGS | Cash | Auto-debit | EMI | Cheque | Other",
      "is_emi": false,
      "is_recurring": false,
      "is_investment": false,
      "is_insurance": false,
      "stress_flag": false
    }
  ],
  "stress_indicators": {
    "notes": "human-readable summary of financial friction or stress events if any"
  },
  "behavioral_insights": {
    "post_payday_splurge": false,
    "top_vendors": [],
    "spending_pattern": null
  }
}

CRITICAL EXTRACTION RULES — follow ALL of these without exception:

CURRENCY:
- Detect currency from: rupee sign (₹→INR), dollar ($→USD), pound (£→GBP), euro (€→EUR), statement header, bank origin.
- If truly unknown, use {"code":"UNKNOWN","symbol":"?","locale":"en","detected_from":"inferred"}.
- NEVER default to INR if the statement is clearly from a USD/GBP/EUR bank.

BALANCES (reconciliation anchors):
- Extract opening_balance and closing_balance exactly as printed — do not compute.
- Extract statement_total_credit and statement_total_debit from the statement summary row if present.
- If a value isn't printed, use null. Never invent balances.

TRANSACTIONS — accuracy mandate (NO COMPRESSION ALLOWED):
- Extract EVERY SINGLE transaction row EXACTLY as it appears. 
- DO NOT GROUP OR SUM identical-looking entries. If there are three ₹10.80 charges on the same day, output THREE separate identical json objects!
- Multi-line description entries: merge all lines of one transaction into one JSON object.
- amount is ALWAYS a positive decimal. NEVER round amounts (use exact 1234.56, not 1235).
- balance_after: Look at the running balance column for that row. Use it if available, else null.

CRITICAL FLOW RULE (Debit vs Credit Absolute Rule):
- `flow` must be exactly 'credit' (money in / deposit) or 'debit' (money out / withdrawal).
- DO NOT GUESS BASED ON VAGUE WORDS.
- Look at the RUNNING BALANCE col: If the balance INCREASES after the transaction, it is ALWAYS a CREDIT. If the balance DECREASES, it is ALWAYS a DEBIT. This mathematical rule overrides everything!

CATEGORY CLASSIFICATION — strict mapping:
- Salary, pension, business credits → "Income"
- Rent, maintenance, home loan → "Housing"
- Petrol, fuel, auto, metro, cab → "Transportation"
- Restaurant, zomato, swiggy, cafe → "Food & Dining"
- Grocery store, supermarket, DMart → "Food & Dining" / sub_category:"Groceries"
- Netflix, Spotify, Amazon Prime, Hotstar → "Subscriptions"
- Electricity, water, gas, broadband, mobile recharge → "Utilities"
- LIC, health/term/vehicle insurance → "Insurance"
- SIP, mutual fund, PPF, NPS, RD, FD, stocks → "Investments"
- School fees, tuition, exam, coaching → "Education"
- ATM withdrawal, cash → "Cash & ATM"
- Hospital, pharmacy, doctor → "Health & Wellness"
- EMI, NACH, loan repayment → "EMIs"
- Internal transfer, own account → "Transfers"
- Set "Other" only when none of the above applies.

FLAGS:
- is_emi: true for NACH/ECS/EMI/loan repayments
- is_recurring: true when you see this merchant+similar_amount across multiple months
- is_investment: true for SIP/MF/PPF/NPS/FD/RD/stocks
- is_insurance: true for LIC/health/term/vehicle premiums
- stress_flag: true for bounced cheque / overdraft / penalty / late fee charges

BEHAVIORAL:
- post_payday_splurge: true if spending surges within 7 days after biggest credit
- cash_reliance_pct: ATM+cash debits / total debits × 100 (round to 1 decimal)
- top_vendors: top 5 merchant names by frequency of debit
"""

SUMMARY_PROMPT_TEMPLATE = """You are a Senior Financial Analyst at a premium private bank.
Write a professional, insight-dense narrative (max 160 words) for the client based ONLY on the verified facts below.

RULES:
- Use ONLY the exact numbers provided. Never invent or round figures.
- If reconciliation shows a mismatch, acknowledge it (e.g., "Note: minor data variance detected").
- Structure: 1-2 sentences on income health → expense analysis → savings/investment health → 1 key risk → 1 specific actionable.
- Currency context: use the correct currency symbol (from currency.symbol), not assumed ₹.
- Tone: calm, precise, premium — like a real wealth manager's report.

Verified Facts:
{facts_json}
"""


def _parse_json_loose(text: str) -> dict[str, Any]:
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def _map_gemini_error(status_code: int, body: str) -> tuple[int, str]:
    detail = ""
    try:
        detail = json.loads(body).get("error", {}).get("message", "")
    except Exception:
        pass
    print(f"[gemini] HTTP {status_code} | {detail[:180]!r}")
    low = body.lower()
    if status_code in (401, 403) or "api key" in low or "permission" in low:
        return 401, "Invalid Gemini API key. Check at https://aistudio.google.com/apikey"
    if status_code == 429:
        hint = " (daily quota exhausted — resets midnight Pacific. Use CSV to bypass.)" if "per_day" in low or "daily" in low else " (per-minute limit — backoff active.)"
        return 429, f"Gemini rate limit.{hint}"
    if status_code in (500, 503):
        return 502, "Gemini temporarily unavailable. Retry in a moment."
    if status_code == 504:
        return 504, "Gemini timed out. Try a smaller statement."
    return 502, f"Gemini request failed (HTTP {status_code})."


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
    models_to_try = [primary_model]
    if primary_model != FALLBACK_MODEL:
        models_to_try.append(FALLBACK_MODEL)
    last_response: httpx.Response | None = None
    for model in models_to_try:
        url = url_template.format(model=model)
        print(f"[gemini] {operation}: model={model}")
        async with httpx.AsyncClient(timeout=settings.gemini_timeout_seconds) as client:
            for attempt in range(MAX_RETRIES_PER_MODEL + 1):
                try:
                    r = await client.post(url, params={"key": api_key}, json=body)
                except httpx.TimeoutException:
                    if attempt >= MAX_RETRIES_PER_MODEL:
                        raise GeminiHttpError(504, "Gemini timed out.")
                    await asyncio.sleep(_jitter_backoff(attempt))
                    continue
                if r.status_code == 200:
                    print(f"[gemini] {operation}: ✓ {model}")
                    return r, model
                if r.status_code in (429, 503) and attempt < MAX_RETRIES_PER_MODEL:
                    ra = r.headers.get("retry-after")
                    wait = min(float(ra), MAX_BACKOFF_SECONDS) if ra else _jitter_backoff(attempt)
                    print(f"[gemini] {operation}: {r.status_code} attempt {attempt+1}, wait {wait:.1f}s")
                    await asyncio.sleep(wait)
                    continue
                last_response = r
                break
            else:
                last_response = r  # type: ignore[possibly-undefined]
        if last_response is not None and last_response.status_code in (429, 503):
            if model != FALLBACK_MODEL:
                print(f"[gemini] {operation}: retries exhausted on {model} → trying fallback")
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
    Returns rich dict:
      transactions, currency, balances, profile, income_profile, stress_indicators, behavioral_insights
    """
    if len(pdf_bytes) > settings.max_upload_bytes:
        raise ValueError("PDF exceeds upload limit")
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
        "generation_config": {"temperature": 0.02, "response_mime_type": "application/json"},
    }
    print(f"[gemini] extract: PDF={len(pdf_bytes)//1024}kB, model={settings.gemini_model}")
    r, model_used = await _gemini_post_with_retry(
        url_template, api_key, body, settings.gemini_model, settings, "extract"
    )
    if r.status_code != 200:
        code, msg = _map_gemini_error(r.status_code, r.text)
        if r.status_code == 429:
            msg += " Use CSV/XLS export for zero-quota processing."
        raise GeminiHttpError(code, msg)
    try:
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = _parse_json_loose(text)
    except Exception as e:
        print(f"[gemini] extract: bad response. Body[:500]: {r.text[:500]}")
        raise GeminiHttpError(502, "Gemini returned unexpected format. Try CSV export.") from e

    txs = parsed.get("transactions")
    if not isinstance(txs, list):
        raise GeminiHttpError(502, "Gemini JSON missing 'transactions' array.")

    out = [t for t in txs if isinstance(t, dict)]
    print(f"[gemini] extract: ✓ {len(out)} tx (model={model_used})")

    return {
        "transactions": out,
        "currency": parsed.get("currency") or {"code": "INR", "symbol": "₹", "locale": "en-IN", "detected_from": "default"},
        "balances": parsed.get("balances") or {},
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
        "generation_config": {"temperature": 0.3, "max_output_tokens": 800},
    }

    class _LimitedTimeout:
        def __init__(self, s: Settings):
            self._s = s
            self.gemini_timeout_seconds = min(s.gemini_timeout_seconds, 60.0)
            self.gemini_model = s.gemini_model
        def __getattr__(self, n: str):
            return getattr(self._s, n)

    # DUAL-MODEL UPGRADE: Try gemini-2.5-pro first for best qualitative logic, then fallback to user's setting
    primary_model = "gemini-2.5-pro"
    models_to_try = [primary_model]
    if settings.gemini_model != primary_model:
        models_to_try.append(settings.gemini_model)
    if FALLBACK_MODEL not in models_to_try:
        models_to_try.append(FALLBACK_MODEL)

    last_response: httpx.Response | None = None
    settings_override = _LimitedTimeout(settings)

    for model in models_to_try:
        url = url_template.format(model=model)
        print(f"[gemini] summary: model={model}")
        
        async with httpx.AsyncClient(timeout=settings_override.gemini_timeout_seconds) as client:
            r = await client.post(url, params={"key": api_key}, json=body)
            if r.status_code == 200:
                print(f"[gemini] summary: ✓ {model}")
                try:
                    return str(r.json()["candidates"][0]["content"]["parts"][0]["text"]).strip()
                except Exception as e:
                    raise GeminiHttpError(502, "Could not read Gemini summary.") from e
            elif r.status_code in (429, 503):
                print(f"[gemini] summary: {r.status_code} on {model} → trying fallback")
                last_response = r
                continue
            else:
                last_response = r
                break
                
    if last_response is not None:
        code, msg = _map_gemini_error(last_response.status_code, last_response.text)
        raise GeminiHttpError(last_response.status_code if last_response.status_code in (401, 403, 429) else 502, msg)
        
    raise GeminiHttpError(502, "Summary generation failed across all models.")


class GeminiHttpError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)
