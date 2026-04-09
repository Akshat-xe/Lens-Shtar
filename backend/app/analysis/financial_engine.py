"""
financial_engine.py — Bank-grade analytics with reconciliation, currency intelligence,
precise decimal arithmetic, fixed/variable split, and full behavioral metrics.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.analysis.models import NormalizedTransaction

_EMI_HINT = re.compile(
    r"\bemi\b|loan\b|nach\b|ach\b|auto\s*debit|si\s|standing\s*instr|ecs\b|mortgage|finance",
    re.I,
)
_SUBSCRIPTION_HINT = re.compile(
    r"netflix|spotify|youtube\s*premium|prime\s*video|apple\.com|google\s*one|dropbox|notion"
    r"|cursor|github|openai|chatgpt|hotstar|zee5|sonyliv|jiocinema|mxplayer|disney",
    re.I,
)
_INVESTMENT_HINT = re.compile(
    r"\bsip\b|mutual\s*fund|nps\b|ppf\b|elss\b|mf\b|equity|zerodha|groww|kuvera|coin\b"
    r"|recurring\s*deposit|\brd\b|\bfd\b|demat",
    re.I,
)
_INSURANCE_HINT = re.compile(
    r"\blic\b|insurance|premium|policy|hdfc\s*life|icici\s*pru|bajaj\s*allianz|star\s*health|care\s*health",
    re.I,
)
_ATM_HINT = re.compile(r"\batm\b|cash\s*withdrawal|cash\s*debit|atw\b", re.I)

# Reconciliation tolerance — amounts within ±1.00 of statement figures are "acceptable"
RECON_TOLERANCE = Decimal("1.00")


def _d(v: float | int | str | None) -> Decimal:
    """Convert to Decimal with 2dp precision."""
    if v is None:
        return Decimal("0.00")
    try:
        return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _month_key(iso_date: str) -> str:
    return iso_date[:7]


# ── Currency Intelligence ─────────────────────────────────────────────────────
_CURRENCY_SYMBOL_MAP = {
    "INR": "₹", "USD": "$", "EUR": "€", "GBP": "£",
    "JPY": "¥", "CAD": "CA$", "AUD": "A$", "SGD": "S$", "AED": "د.إ",
}
_LOCALE_MAP = {
    "INR": "en-IN", "USD": "en-US", "EUR": "en-DE", "GBP": "en-GB",
}


def resolve_currency(gemini_currency: dict[str, Any] | None) -> dict[str, str]:
    """Return normalised currency dict: code, symbol, locale."""
    gc = gemini_currency or {}
    code = str(gc.get("code") or "INR").upper().strip()
    if code in ("UNKNOWN", "", "?"):
        code = "INR"
    symbol = gc.get("symbol") or _CURRENCY_SYMBOL_MAP.get(code, code + " ")
    locale = gc.get("locale") or _LOCALE_MAP.get(code, "en-US")
    return {
        "code": code,
        "symbol": str(symbol),
        "locale": str(locale),
        "detected_from": str(gc.get("detected_from") or "default"),
    }


# ── Reconciliation Engine ─────────────────────────────────────────────────────
def run_reconciliation(
    computed_credits: Decimal,
    computed_debits: Decimal,
    balances: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate computed totals against statement-printed figures.
    Returns reconciliation result with confidence and mismatch details.
    """
    stmt_credit = _d(balances.get("statement_total_credit"))
    stmt_debit = _d(balances.get("statement_total_debit"))
    opening = _d(balances.get("opening_balance"))
    closing = _d(balances.get("closing_balance"))

    issues: list[str] = []
    checks: list[dict[str, Any]] = []

    def _check(label: str, computed: Decimal, expected: Decimal | None, unit: str = ""):
        if expected is None or expected == Decimal("0.00"):
            checks.append({"label": label, "status": "skipped", "reason": "not in statement"})
            return True
        diff = abs(computed - expected)
        ok = diff <= RECON_TOLERANCE
        checks.append({
            "label": label,
            "computed": float(computed),
            "statement": float(expected),
            "diff": float(diff),
            "status": "matched" if ok else "mismatch",
        })
        if not ok:
            issues.append(f"{label}: computed {unit}{float(computed):,.2f} vs statement {unit}{float(expected):,.2f} (Δ{float(diff):,.2f})")
        return ok

    credit_ok = _check("Total Money In", computed_credits, stmt_credit if stmt_credit else None)
    debit_ok = _check("Total Money Out", computed_debits, stmt_debit if stmt_debit else None)

    # Balance progression: opening + credits - debits ≈ closing
    balance_ok = True
    if opening != Decimal("0.00") and closing != Decimal("0.00"):
        expected_closing = opening + computed_credits - computed_debits
        balance_diff = abs(expected_closing - closing)
        balance_ok = balance_diff <= RECON_TOLERANCE
        checks.append({
            "label": "Balance Progression",
            "computed": float(expected_closing),
            "statement": float(closing),
            "diff": float(balance_diff),
            "status": "matched" if balance_ok else "mismatch",
        })
        if not balance_ok:
            issues.append(f"Balance: {float(opening):,.2f} + credits - debits = {float(expected_closing):,.2f}, but statement closing is {float(closing):,.2f}")

    all_ok = credit_ok and debit_ok and balance_ok
    # Confidence: all matched + balances present = High; some skipped = Medium; mismatch = Low
    has_statement_data = any(c["status"] != "skipped" for c in checks)
    if all_ok and has_statement_data:
        confidence = "High"
    elif all_ok and not has_statement_data:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "status": "verified" if all_ok else "mismatch",
        "confidence": confidence,
        "checks": checks,
        "issues": issues,
        "opening_balance": float(opening) if opening else None,
        "closing_balance": float(closing) if closing else None,
        "has_statement_anchors": has_statement_data,
    }


# ── Main Engine ───────────────────────────────────────────────────────────────
def run_financial_engine(
    transactions: list[NormalizedTransaction],
    gemini_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = gemini_meta or {}

    # Use Decimal for all accumulation — eliminates floating-point drift
    income = Decimal("0.00")
    expenses = Decimal("0.00")
    upi_spend = Decimal("0.00")
    atm_spend = Decimal("0.00")
    investment_total = Decimal("0.00")
    insurance_total = Decimal("0.00")
    emi_total = Decimal("0.00")

    category_debit_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    sub_cat_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    monthly_income: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    monthly_expense: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    payment_method_count: Counter = Counter()
    merchant_spend: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

    # ── RULE ENGINE PRE-PASS: Mathematical flow verification ──
    # If standard running balances exist, they dictate absolute flow (debit vs credit).
    dates = [t["date"] for t in transactions if t.get("date")]
    direction_is_forward = True
    if len(dates) >= 2 and dates[0] > dates[-1]:
        direction_is_forward = False  # Reverse-chronological PDF

    seq = transactions if direction_is_forward else list(reversed(transactions))
    prev_bal = None
    for t in seq:
        raw_bal = t.get("balance_after")
        if raw_bal is not None:
            bal = _d(raw_bal)
            amt = _d(t.get("amount", 0))
            if prev_bal is not None and amt > Decimal("0.00"):
                delta = bal - prev_bal
                # If mathematically exact, override AI's flow label
                if abs(abs(delta) - amt) <= Decimal("0.01"):
                    t["flow"] = "credit" if delta > 0 else "debit"
            prev_bal = bal

    for t in transactions:
        amt = _d(t["amount"])
        blob = f"{t['merchant_clean']} {t.get('description', '')}".lower()
        pm = (t.get("payment_method") or "Other").strip()

        if t["flow"] == "credit":
            income += amt
            monthly_income[_month_key(t["date"])] += amt
        else:
            expenses += amt
            monthly_expense[_month_key(t["date"])] += amt
            cat = t.get("category") or "Other"
            category_debit_totals[cat] += amt
            sub_cat = t.get("sub_category") or ""
            if sub_cat:
                sub_cat_totals[sub_cat] += amt
            payment_method_count[pm] += 1

            if "upi" in pm.lower() or ("upi" in blob and pm in ("Other", "")):
                upi_spend += amt
            if _ATM_HINT.search(blob) or "cash" in pm.lower():
                atm_spend += amt
            if t.get("is_investment") or _INVESTMENT_HINT.search(blob):
                investment_total += amt
            if t.get("is_insurance") or _INSURANCE_HINT.search(blob):
                insurance_total += amt
            if t.get("is_emi") or _EMI_HINT.search(blob):
                emi_total += amt

            merchant_spend[t["merchant_clean"].lower()[:80]] += amt

    # Precise savings — strict: income - expenses (no approximation)
    savings = income - expenses
    savings_rate_pct = float((savings / income * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if income > 0 else 0.0
    investment_rate_pct = float((investment_total / income * Decimal("100")).quantize(Decimal("0.01"))) if income > 0 else 0.0

    # Fixed vs Variable
    fixed_cats = {"EMIs", "Insurance", "Housing", "Utilities", "Subscriptions", "Investments", "Education"}
    fixed_spend = sum((v for k, v in category_debit_totals.items() if k in fixed_cats), Decimal("0.00"))
    variable_spend = max(Decimal("0.00"), expenses - fixed_spend)
    fixed_ratio = float((fixed_spend / expenses * Decimal("100")).quantize(Decimal("0.01"))) if expenses > 0 else 0.0

    # Category breakdown
    debit_total = expenses or Decimal("1.00")
    category_breakdown = [
        {
            "category": k,
            "amount": float(v.quantize(Decimal("0.01"))),
            "pct": float((v / debit_total * Decimal("100")).quantize(Decimal("0.01"))),
        }
        for k, v in sorted(category_debit_totals.items(), key=lambda x: -x[1])
    ]

    sub_cat_breakdown = [
        {"sub_category": k, "amount": float(v.quantize(Decimal("0.01")))}
        for k, v in sorted(sub_cat_totals.items(), key=lambda x: -x[1])[:10]
    ]

    # Monthly flow — all precise
    months_sorted = sorted(set(monthly_income.keys()) | set(monthly_expense.keys()))
    monthly_savings = {m: monthly_income[m] - monthly_expense[m] for m in months_sorted}
    monthly_flow = {
        "labels": months_sorted,
        "income":   [float(monthly_income[m].quantize(Decimal("0.01")))  for m in months_sorted],
        "expenses": [float(monthly_expense[m].quantize(Decimal("0.01"))) for m in months_sorted],
        "savings":  [float(monthly_savings[m].quantize(Decimal("0.01"))) for m in months_sorted],
    }

    # Payment distribution
    total_tx = len(transactions)
    payment_dist = [
        {"method": m, "count": c, "pct": round(c / total_tx * 100, 1) if total_tx else 0}
        for m, c in payment_method_count.most_common(8)
    ]

    # Top merchants by spend
    top_merchants = [
        {"merchant": k.title(), "amount": float(v.quantize(Decimal("0.01")))}
        for k, v in sorted(merchant_spend.items(), key=lambda x: -x[1])[:10]
    ]

    emi_candidates = _detect_emi_candidates(transactions)
    emi_monthly_estimate = float(sum((_d(x["amount"]) for x in emi_candidates), Decimal("0.00")).quantize(Decimal("0.01")))
    recurring = _detect_recurring(transactions)

    tx_out: list[dict[str, Any]] = [
        {
            "date": t["date"],
            "amount": float(_d(t["amount"])),
            "flow": t["flow"],
            "merchant": t["merchant_clean"],
            "merchant_raw": t.get("merchant_raw") or t["merchant_clean"],
            "category": t.get("category") or "Other",
            "sub_category": t.get("sub_category") or "",
            "description": t.get("description") or "",
            "payment_method": t.get("payment_method") or "Other",
            "is_emi": bool(t.get("is_emi")),
            "is_recurring": bool(t.get("is_recurring")),
            "is_investment": bool(t.get("is_investment")),
            "is_insurance": bool(t.get("is_insurance")),
            "stress_flag": bool(t.get("stress_flag")),
        }
        for t in sorted(transactions, key=lambda x: x["date"], reverse=True)
    ]

    # Currency
    currency = resolve_currency(meta.get("currency"))

    # Reconciliation
    balances = meta.get("balances") or {}
    reconciliation = run_reconciliation(income, expenses, balances)

    # KPIs — exact Decimal→float conversion at the very end
    kpis = {
        "total_income":        float(income.quantize(Decimal("0.01"))),
        "total_expenses":      float(expenses.quantize(Decimal("0.01"))),
        "net_savings":         float(savings.quantize(Decimal("0.01"))),
        "savings_rate_pct":    savings_rate_pct,
        "investment_total":    float(investment_total.quantize(Decimal("0.01"))),
        "investment_rate_pct": investment_rate_pct,
        "insurance_total":     float(insurance_total.quantize(Decimal("0.01"))),
        "emi_total":           float(emi_total.quantize(Decimal("0.01"))),
        "emi_monthly_estimate": emi_monthly_estimate,
        "upi_spend":           float(upi_spend.quantize(Decimal("0.01"))),
        "atm_spend":           float(atm_spend.quantize(Decimal("0.01"))),
        "cash_reliance_pct":   float((atm_spend / expenses * Decimal("100")).quantize(Decimal("0.01"))) if expenses > 0 else 0.0,
        "fixed_spend":         float(fixed_spend.quantize(Decimal("0.01"))),
        "variable_spend":      float(variable_spend.quantize(Decimal("0.01"))),
        "fixed_ratio_pct":     fixed_ratio,
        "variable_ratio_pct":  round(100.0 - fixed_ratio, 2),
        "transaction_count":   len(transactions),
        # Legacy aliases
        "income":   float(income.quantize(Decimal("0.01"))),
        "expenses": float(expenses.quantize(Decimal("0.01"))),
        "savings":  float(savings.quantize(Decimal("0.01"))),
    }

    charts = {
        "category_breakdown":   category_breakdown[:14],
        "sub_category_breakdown": sub_cat_breakdown,
        "monthly_flow":         monthly_flow,
        "payment_distribution": payment_dist,
        "top_merchants":        top_merchants,
    }

    return {
        "kpis":                kpis,
        "charts":              charts,
        "emi_candidates":      emi_candidates,
        "recurring":           recurring,
        "transactions":        tx_out,
        "currency":            currency,
        "reconciliation":      reconciliation,
        "profile":             meta.get("profile") or {},
        "income_profile":      meta.get("income_profile") or {},
        "stress_indicators":   meta.get("stress_indicators") or {},
        "behavioral_insights": meta.get("behavioral_insights") or {},
    }


def _detect_emi_candidates(transactions: Iterable[NormalizedTransaction]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for t in transactions:
        if t["flow"] != "debit":
            continue
        blob = f"{t['merchant_clean']} {t.get('description','')}"
        if not _EMI_HINT.search(blob) and t.get("payment_method") != "EMI" and not t.get("is_emi"):
            continue
        key = (t["merchant_clean"], str(_d(t["amount"])), t["date"][:7])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "merchant": t["merchant_clean"],
            "amount": float(_d(t["amount"])),
            "month": t["date"][:7],
            "confidence": "high" if _EMI_HINT.search(blob) else "medium",
        })
    out.sort(key=lambda x: -x["amount"])
    return out[:20]


def _detect_recurring(transactions: Iterable[NormalizedTransaction]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, int], list[NormalizedTransaction]] = defaultdict(list)
    for t in transactions:
        if t["flow"] != "debit" or float(t["amount"]) < 10:
            continue
        r = int(round(float(t["amount"]) / 50.0) * 50)
        key = (t["merchant_clean"].lower()[:60], r)
        buckets[key].append(t)

    out: list[dict[str, Any]] = []
    for (_, _r), items in buckets.items():
        months = {x["date"][:7] for x in items}
        if len(items) < 2 or (len(months) < 2 and len(items) < 3):
            continue
        avg = float(sum(_d(x["amount"]) for x in items) / len(items))
        out.append({
            "merchant": items[0]["merchant_clean"],
            "rounded_amount_inr": _r,
            "occurrences": len(items),
            "months_spanned": len(months),
            "avg_amount": round(avg, 2),
            "is_subscription": bool(_SUBSCRIPTION_HINT.search(items[0]["merchant_clean"])),
            "is_investment": bool(_INVESTMENT_HINT.search(items[0]["merchant_clean"])),
        })
    out.sort(key=lambda x: (-x["occurrences"], -x["avg_amount"]))
    return out[:25]


def build_summary_facts(engine_out: dict[str, Any]) -> dict[str, Any]:
    """Safe, non-sensitive aggregates for Gemini narrative."""
    k = engine_out["kpis"]
    recon = engine_out.get("reconciliation") or {}
    return {
        "currency": engine_out.get("currency") or {"code": "INR", "symbol": "₹"},
        "kpis": {
            "total_income":        k["total_income"],
            "total_expenses":      k["total_expenses"],
            "net_savings":         k["net_savings"],
            "savings_rate_pct":    k["savings_rate_pct"],
            "investment_total":    k["investment_total"],
            "investment_rate_pct": k["investment_rate_pct"],
            "emi_total":           k["emi_total"],
            "cash_reliance_pct":   k["cash_reliance_pct"],
            "fixed_ratio_pct":     k["fixed_ratio_pct"],
        },
        "top_spending_categories":   engine_out["charts"]["category_breakdown"][:5],
        "emi_count":                 len(engine_out.get("emi_candidates", [])),
        "recurring_patterns_count":  len(engine_out.get("recurring", [])),
        "period_months":             engine_out["charts"]["monthly_flow"]["labels"],
        "profile":                   engine_out.get("profile") or {},
        "income_profile":            engine_out.get("income_profile") or {},
        "stress_indicators":         engine_out.get("stress_indicators") or {},
        "behavioral_insights":       engine_out.get("behavioral_insights") or {},
        "reconciliation_status":     recon.get("status"),
        "reconciliation_confidence": recon.get("confidence"),
        "reconciliation_issues":     recon.get("issues") or [],
    }


def transaction_date_span(transactions: list[NormalizedTransaction]) -> tuple[str | None, str | None]:
    if not transactions:
        return None, None
    dates = [t["date"] for t in transactions]
    return min(dates), max(dates)
