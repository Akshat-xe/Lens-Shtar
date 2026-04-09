from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from app.analysis.models import NormalizedTransaction

_MERCHANT_CLEAN_RE = re.compile(r"\s+")
_UPI_MARKERS = ("upi", "/u", "upi/", "@ybl", "@oksbi", "@paytm", "@ibl", "imps", "neft", "rtgs")


def _parse_date(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and str(val) == "nan"):
        return None
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%Y-%m-%d")
        except Exception:
            pass
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s[:11], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        if isinstance(val, (int, float)):
            from datetime import timedelta
            base = datetime(1899, 12, 30)
            d = base + timedelta(days=float(val))
            return d.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None


def _to_amount(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if str(val) == "nan":
            return None
        return abs(float(val))
    s = str(val).strip().replace(",", "")
    if not s:
        return None
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s in "-.":
        return None
    try:
        return abs(float(s))
    except ValueError:
        return None


def _clean_merchant(s: str) -> str:
    t = _MERCHANT_CLEAN_RE.sub(" ", (s or "").strip())
    return t[:200] if t else "Unknown"


def _infer_payment_method(merchant: str, description: str) -> str:
    blob = f"{merchant} {description}".lower()
    if any(m in blob for m in _UPI_MARKERS):
        return "UPI"
    if "card" in blob or "pos" in blob:
        return "Card"
    if "nach" in blob or "ecs" in blob or "si " in blob or "standing" in blob:
        return "Auto-debit"
    if "emi" in blob or "loan" in blob:
        return "EMI"
    if "neft" in blob:
        return "NEFT"
    if "rtgs" in blob:
        return "RTGS"
    if "imps" in blob:
        return "IMPS"
    if "atm" in blob or "cash" in blob:
        return "Cash"
    return "Other"


def normalize_transaction_row(row: dict[str, Any]) -> NormalizedTransaction | None:
    date_s = _parse_date(row.get("date"))
    if not date_s:
        return None

    flow_raw = str(
        row.get("flow") or row.get("debit_credit") or row.get("type") or ""
    ).lower().strip()
    amount = _to_amount(row.get("amount"))
    if amount is None or amount <= 0:
        return None

    if flow_raw in ("credit", "cr", "in", "inflow", "deposit"):
        flow: str = "credit"
    elif flow_raw in ("debit", "dr", "out", "outflow", "withdrawal"):
        flow = "debit"
    else:
        raw_amt = row.get("signed_amount") or row.get("signed")
        if raw_amt is not None:
            try:
                sa = float(str(raw_amt).replace(",", ""))
                flow = "credit" if sa >= 0 else "debit"
                amount = abs(sa)
            except ValueError:
                flow = "debit"
        else:
            flow = "debit"

    merchant_raw = str(row.get("merchant_raw") or row.get("description") or row.get("narration") or "")[:500]
    merchant_clean = str(row.get("merchant_clean") or merchant_raw or "Unknown")[:500]
    merchant_clean = _clean_merchant(merchant_clean)
    description = _clean_merchant(str(row.get("description") or merchant_raw or "")[:500])
    category_ai = str(row.get("category") or row.get("category_suggestion") or "Other").strip() or "Other"
    sub_category_ai = str(row.get("sub_category") or "").strip()
    
    from app.analysis.classification import apply_classification_overrides
    merchant_clean, category, sub_category = apply_classification_overrides(
        merchant_raw, merchant_clean, category_ai, sub_category_ai
    )
    
    payment = str(row.get("payment_method") or "").strip()
    if not payment:
        payment = _infer_payment_method(merchant_clean, description)

    return NormalizedTransaction(
        date=date_s,
        amount=float(amount),
        flow=flow,  # type: ignore[arg-type]
        balance_after=_to_amount(row.get("balance_after")) if row.get("balance_after") is not None else None,
        merchant_raw=merchant_raw or merchant_clean,
        merchant_clean=merchant_clean,
        category=category[:80],
        sub_category=sub_category[:80],
        description=description,
        payment_method=payment[:40],
        is_emi=bool(row.get("is_emi", False)),
        is_recurring=bool(row.get("is_recurring", False)),
        is_investment=bool(row.get("is_investment", False)),
        is_insurance=bool(row.get("is_insurance", False)),
        stress_flag=bool(row.get("stress_flag", False)),
    )


def validate_and_normalize(raw_rows: list[dict[str, Any]]) -> list[NormalizedTransaction]:
    parsed: list[NormalizedTransaction] = []
    for r in raw_rows:
        n = normalize_transaction_row(r)
        if n:
            parsed.append(n)
    
    # We DO NOT arbitrarily deduplicate identical transactions on the same day anymore.
    # If the LLM saw multiple identical charges, we retain them.
    return parsed
