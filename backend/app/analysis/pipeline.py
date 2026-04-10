"""
pipeline.py — Upload processing pipeline.
Handles PDF (via Gemini) and CSV/XLS (local) extraction, then runs the financial engine.
"""
from __future__ import annotations

import uuid
from typing import Any

from app import session_store
from app.analysis import store as analysis_store
from app.analysis.financial_engine import build_summary_facts, run_financial_engine
from app.analysis.gemini_client import GeminiHttpError, extract_transactions_from_pdf, generate_ai_summary
from app.analysis.leaks import detect_money_leaks
from app.analysis.spreadsheet_parser import parse_csv, parse_excel
from app.analysis.suggestions import build_savings_suggestions, rule_based_fallback_summary
from app.analysis.validation import validate_and_normalize
from app.config import Settings


ALLOWED_SUFFIX = {".pdf", ".csv", ".xls", ".xlsx"}


def _suffix(name: str) -> str:
    if not name or "." not in name:
        return ""
    return name[name.rfind("."):].lower()


async def run_upload_pipeline(
    *,
    user_id: str,
    filename: str,
    content: bytes,
    content_type: str | None,
    settings: Settings,
    include_ai_summary: bool = True,
) -> dict[str, Any]:
    if len(content) > settings.max_upload_bytes:
        raise FileTooLargeError(settings.max_upload_bytes)

    suf = _suffix(filename or "")
    if suf not in ALLOWED_SUFFIX:
        raise UnsupportedFileError(", ".join(sorted(ALLOWED_SUFFIX)))

    api_key = session_store.get_gemini_key(user_id)
    if not api_key:
        raise MissingApiKeyError()

    warnings: list[str] = []
    gemini_used_for_pdf = False
    raw_rows: list[dict[str, Any]] = []
    gemini_meta: dict[str, Any] = {}  # profile, income_profile, stress_indicators, behavioral_insights

    if suf == ".pdf":
        gemini_used_for_pdf = True
        try:
            result = await extract_transactions_from_pdf(api_key, content, settings)
            raw_rows = result.get("transactions", [])
            gemini_meta = {
                "profile": result.get("profile") or {},
                "income_profile": result.get("income_profile") or {},
                "stress_indicators": result.get("stress_indicators") or {},
                "behavioral_insights": result.get("behavioral_insights") or {},
                "currency": result.get("currency") or {},
                "balances": result.get("balances") or {},
            }
        except GeminiHttpError as e:
            if e.status_code == 429:
                print(f"[pipeline] PDF extraction blocked by 429: {e.message}")
                raise GeminiHttpError(
                    429,
                    "Gemini rate limit hit while reading your PDF. "
                    "Wait 60 seconds and retry, OR export your statement as CSV/XLS — "
                    "those are processed locally with zero Gemini quota."
                ) from e
            raise
        except ValueError as e:
            raise BadInputError(str(e)) from e
        if not raw_rows:
            warnings.append("Gemini returned no transactions — statement may be image-only or empty.")
    else:
        try:
            if suf == ".csv":
                raw_rows = parse_csv(content)
            else:
                raw_rows = parse_excel(content, suf)
        except Exception as e:
            raise BadInputError(f"Could not parse spreadsheet: {e}") from e
        if not raw_rows:
            raise BadInputError("No transaction rows found — check column headers or export format.")

    normalized = validate_and_normalize(raw_rows)
    if not normalized:
        raise BadInputError(
            "No valid transactions after validation. Ensure dates and amounts are present."
        )

    engine_out = run_financial_engine(normalized, gemini_meta=gemini_meta)
    leaks = detect_money_leaks(normalized, engine_out.get("recurring", []))
    recon_status = engine_out.get("reconciliation", {}).get("status", "mismatch")
    
    if recon_status == "verified":
        suggestions = build_savings_suggestions(
            engine_out["kpis"],
            engine_out["charts"]["category_breakdown"],
            leaks,
            engine_out["kpis"].get("upi_spend", 0.0),
            engine_out.get("behavioral_insights") or {},
        )
    else:
        # Insight Gating: Do not generate smart generic savings if the ledger is broken
        suggestions = {
            "quick_wins": [{
                "title": "⚠️ Ledger Reconciliation Failed",
                "detail": "Actionable insights are paused because the extracted transactions do not mathematically match the statement totals. Please review the highlighted conflicts.",
                "bucket": "System Alert"
            }],
            "monthly_optimization": [],
            "long_term": []
        }

    ai_summary: str | None = None
    ai_summary_error: str | None = None
    
    # Insight Gating: Only run the LLM narrative if the data is structurally verified
    if include_ai_summary and settings.gemini_ai_summary_enabled and recon_status == "verified":
        facts = build_summary_facts(engine_out)
        try:
            ai_summary = await generate_ai_summary(api_key, facts, settings)
        except GeminiHttpError as e:
            print(f"[pipeline] AI summary failed ({e.status_code}): {e.message} — using rule-based fallback.")
            ai_summary_error = e.message
            ai_summary = rule_based_fallback_summary(normalized, engine_out["kpis"])
        except Exception as e:
            print(f"[pipeline] AI summary unexpected error: {e} — using rule-based fallback.")
            ai_summary_error = "AI summary unavailable."
            ai_summary = rule_based_fallback_summary(normalized, engine_out["kpis"])
    else:
        ai_summary = rule_based_fallback_summary(normalized, engine_out["kpis"])

    file_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "filename": filename or "upload",
        "content_type": content_type,
        "kpis": engine_out["kpis"],
        "charts": engine_out["charts"],
        "emi_candidates": engine_out["emi_candidates"],
        "recurring": engine_out["recurring"],
        "leaks": leaks,
        "suggestions": suggestions,
        "transactions": engine_out["transactions"],
        "profile": engine_out.get("profile") or {},
        "income_profile": engine_out.get("income_profile") or {},
        "stress_indicators": engine_out.get("stress_indicators") or {},
        "behavioral_insights": engine_out.get("behavioral_insights") or {},
        "currency": engine_out.get("currency") or {"code": "INR", "symbol": "₹", "locale": "en-IN"},
        "reconciliation": engine_out.get("reconciliation") or {},
        "ai_summary": ai_summary,
        "ai_summary_error": ai_summary_error,
        "meta": {
            "gemini_used_for_pdf": gemini_used_for_pdf,
            "warnings": warnings,
        },
    }

    analysis_store.save_analysis(file_id, user_id, payload)

    return {
        "file_id": file_id,
        "status": "analyzed",
        "transaction_count": len(normalized),
        "kpis": engine_out["kpis"],
        "meta": payload["meta"],
    }


class PipelineError(Exception):
    def http_status(self) -> int:
        return 400


class FileTooLargeError(PipelineError):
    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        super().__init__(f"File too large. Maximum size is {max(1, max_bytes // (1024 * 1024))} MB.")
    def http_status(self) -> int:
        return 413


class UnsupportedFileError(PipelineError):
    def __init__(self, allowed: str) -> None:
        super().__init__(f"Unsupported file type. Allowed: {allowed}.")
    def http_status(self) -> int:
        return 415


class MissingApiKeyError(PipelineError):
    def __init__(self) -> None:
        super().__init__("API key required")
    def http_status(self) -> int:
        return 400


class BadInputError(PipelineError):
    pass
