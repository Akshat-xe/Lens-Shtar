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
    return name[name.rfind(".") :].lower()


async def run_upload_pipeline(
    *,
    user_id: str,
    filename: str,
    content: bytes,
    content_type: str | None,
    settings: Settings,
    include_ai_summary: bool = True,
) -> dict[str, Any]:
    """
    Uses ONLY session_store Gemini key for PDF / optional summary — never a server key.
    """
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

    if suf == ".pdf":
        gemini_used_for_pdf = True
        try:
            raw_rows = await extract_transactions_from_pdf(api_key, content, settings)
        except GeminiHttpError:
            raise
        except ValueError as e:
            raise BadInputError(str(e)) from e
        if not raw_rows:
            warnings.append("Gemini returned no transactions — statement may be unreadable or empty.")
    else:
        try:
            if suf == ".csv":
                raw_rows = parse_csv(content)
            else:
                raw_rows = parse_excel(content, suf)
        except Exception as e:
            raise BadInputError(f"Could not parse spreadsheet: {e}") from e
        if not raw_rows:
            raise BadInputError("No transaction rows found in spreadsheet — check columns or export format.")

    normalized = validate_and_normalize(raw_rows)
    if not normalized:
        raise BadInputError(
            "No valid transactions after validation. Try another export or ensure dates and amounts are present."
        )

    engine_out = run_financial_engine(normalized)
    leaks = detect_money_leaks(normalized, engine_out.get("recurring", []))
    suggestions = build_savings_suggestions(
        engine_out["kpis"],
        engine_out["charts"]["category_breakdown"],
        leaks,
        engine_out["kpis"].get("upi_spend", 0.0),
    )

    ai_summary: str | None = None
    ai_summary_error: str | None = None
    if include_ai_summary and settings.gemini_ai_summary_enabled:
        facts = build_summary_facts(engine_out)
        try:
            ai_summary = await generate_ai_summary(api_key, facts, settings)
        except GeminiHttpError as e:
            ai_summary_error = e.message
            ai_summary = rule_based_fallback_summary(normalized, engine_out["kpis"])
        except Exception:
            ai_summary_error = "AI summary unavailable. Showing rule-based summary instead."
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
    """Base for user-facing pipeline errors."""

    def http_status(self) -> int:
        return 400


class FileTooLargeError(PipelineError):
    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        super().__init__(
            f"File too large. Maximum size is {max(1, max_bytes // (1024 * 1024))} MB for this server."
        )

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
