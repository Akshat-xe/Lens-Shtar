"""
financial_engine.py — Deep analytics engine.
Processes normalized transactions into comprehensive KPIs, charts, and insights.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from app.analysis.models import NormalizedTransaction

_EMI_HINT = re.compile(
    r"\bemi\b|loan\b|nach\b|ach\b|auto\s*debit|si\s|standing\s*instr|ecs\b|mortgage|finance",
    re.I,
)
_SUBSCRIPTION_HINT = re.compile(
    r"netflix|spotify|youtube\s*premium|prime\s*video|apple\.com|google\s*one|dropbox|notion|cursor|github|openai|chatgpt|hotstar|zee5|sonyliv|jiocinema|mxplayer",
    re.I,
)
_INVESTMENT_HINT = re.compile(
    r"\bsip\b|mutual\s*fund|nps\b|ppf\b|elss\b|mf\b|equity|zerodha|groww|kuvera|coin\b|recurring\s*deposit|\brd\b|\bfd\b",
    re.I,
)
_INSURANCE_HINT = re.compile(
    r"\blic\b|insurance|premium|policy|hdfc\s*life|icici\s*pru|bajaj\s*allianz|star\s*health|care\s*health",
    re.I,
)
_ATM_HINT = re.compile(r"\batm\b|cash\s*withdrawal|cash\s*debit|atw\b", re.I)


def _month_key(iso_date: str) -> str:
    return iso_date[:7]


def run_financial_engine(
    transactions: list[NormalizedTransaction],
    gemini_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    income = 0.0
    expenses = 0.0
    upi_spend = 0.0
    atm_spend = 0.0
    investment_total = 0.0
    insurance_total = 0.0
    emi_total = 0.0

    category_debit_totals: dict[str, float] = defaultdict(float)
    sub_cat_totals: dict[str, float] = defaultdict(float)
    monthly_income: dict[str, float] = defaultdict(float)
    monthly_expense: dict[str, float] = defaultdict(float)
    monthly_savings: dict[str, float] = defaultdict(float)
    payment_method_count: Counter = Counter()
    merchant_spend: dict[str, float] = defaultdict(float)
    daily_spend: dict[str, float] = defaultdict(float)

    for t in transactions:
        amt = float(t["amount"])
        blob = f"{t['merchant_clean']} {t['description']}".lower()
        pm = (t.get("payment_method") or "Other").strip()

        if t["flow"] == "credit":
            income += amt
            monthly_income[_month_key(t["date"])] += amt
        else:
            expenses += amt
            monthly_expense[_month_key(t["date"])] += amt
            cat = t["category"]
            category_debit_totals[cat] += amt
            sub_cat = t.get("sub_category") or ""
            if sub_cat:
                sub_cat_totals[sub_cat] += amt
            payment_method_count[pm] += 1

            if "upi" in pm.lower() or ("upi" in blob and pm == "Other"):
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
            daily_spend[t["date"]] += amt

    # Savings per month
    months_sorted = sorted(set(monthly_income.keys()) | set(monthly_expense.keys()))
    for m in months_sorted:
        monthly_savings[m] = round(monthly_income[m] - monthly_expense[m], 2)

    savings = income - expenses
    savings_rate_pct = round((savings / income * 100.0), 1) if income > 0 else 0.0
    investment_rate_pct = round((investment_total / income * 100.0), 1) if income > 0 else 0.0

    # Fixed vs Variable split
    fixed_cats = {"EMIs", "Insurance", "Housing", "Utilities", "Subscriptions", "Investments", "Education"}
    fixed_spend = sum(v for k, v in category_debit_totals.items() if k in fixed_cats)
    variable_spend = max(0.0, expenses - fixed_spend)
    fixed_ratio = round(fixed_spend / expenses * 100, 1) if expenses > 0 else 0.0

    # Category breakdown
    debit_total = sum(category_debit_totals.values()) or 1.0
    category_breakdown = [
        {"category": k, "amount": round(v, 2), "pct": round(v / debit_total * 100.0, 1)}
        for k, v in sorted(category_debit_totals.items(), key=lambda x: -x[1])
    ]

    # Sub-category breakdown (top 10)
    sub_cat_breakdown = [
        {"sub_category": k, "amount": round(v, 2)}
        for k, v in sorted(sub_cat_totals.items(), key=lambda x: -x[1])[:10]
    ]

    # Monthly flow chart data
    monthly_flow = {
        "labels": months_sorted,
        "income": [round(monthly_income[m], 2) for m in months_sorted],
        "expenses": [round(monthly_expense[m], 2) for m in months_sorted],
        "savings": [round(monthly_savings[m], 2) for m in months_sorted],
    }

    # Payment method distribution
    total_tx = len(transactions)
    payment_dist = [
        {"method": m, "count": c, "pct": round(c / total_tx * 100, 1)}
        for m, c in payment_method_count.most_common(8)
    ]

    # Top merchant spend
    top_merchants = [
        {"merchant": k, "amount": round(v, 2)}
        for k, v in sorted(merchant_spend.items(), key=lambda x: -x[1])[:10]
    ]

    emi_candidates = _detect_emi_candidates(transactions)
    emi_monthly_estimate = round(sum(x["amount"] for x in emi_candidates), 2)
    recurring = _detect_recurring(transactions)

    tx_out: list[dict[str, Any]] = [
        {
            "date": t["date"],
            "amount": round(t["amount"], 2),
            "flow": t["flow"],
            "merchant": t["merchant_clean"],
            "merchant_raw": t["merchant_raw"],
            "category": t["category"],
            "sub_category": t.get("sub_category") or "",
            "description": t["description"],
            "payment_method": t["payment_method"],
            "is_emi": t.get("is_emi") or False,
            "is_recurring": t.get("is_recurring") or False,
            "is_investment": t.get("is_investment") or False,
            "is_insurance": t.get("is_insurance") or False,
            "stress_flag": t.get("stress_flag") or False,
        }
        for t in sorted(transactions, key=lambda x: x["date"], reverse=True)
    ]

    kpis = {
        "total_income": round(income, 2),
        "total_expenses": round(expenses, 2),
        "net_savings": round(savings, 2),
        "savings_rate_pct": savings_rate_pct,
        "investment_total": round(investment_total, 2),
        "investment_rate_pct": investment_rate_pct,
        "insurance_total": round(insurance_total, 2),
        "emi_total": round(emi_total, 2),
        "emi_monthly_estimate": emi_monthly_estimate,
        "upi_spend": round(upi_spend, 2),
        "atm_spend": round(atm_spend, 2),
        "cash_reliance_pct": round(atm_spend / expenses * 100, 1) if expenses > 0 else 0.0,
        "fixed_spend": round(fixed_spend, 2),
        "variable_spend": round(variable_spend, 2),
        "fixed_ratio_pct": fixed_ratio,
        "variable_ratio_pct": round(100.0 - fixed_ratio, 1),
        "transaction_count": len(transactions),
        # Legacy aliases so old frontend fields still work
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "savings": round(savings, 2),
    }

    charts = {
        "category_breakdown": category_breakdown[:14],
        "sub_category_breakdown": sub_cat_breakdown,
        "monthly_flow": monthly_flow,
        "payment_distribution": payment_dist,
        "top_merchants": top_merchants,
    }

    # Attach gemini_meta extras if available
    profile = {}
    income_profile = {}
    stress_indicators = {}
    behavioral_insights = {}
    if gemini_meta:
        profile = gemini_meta.get("profile") or {}
        income_profile = gemini_meta.get("income_profile") or {}
        stress_indicators = gemini_meta.get("stress_indicators") or {}
        behavioral_insights = gemini_meta.get("behavioral_insights") or {}

    return {
        "kpis": kpis,
        "charts": charts,
        "emi_candidates": emi_candidates,
        "recurring": recurring,
        "transactions": tx_out,
        "profile": profile,
        "income_profile": income_profile,
        "stress_indicators": stress_indicators,
        "behavioral_insights": behavioral_insights,
    }


def _detect_emi_candidates(transactions: Iterable[NormalizedTransaction]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, float, str]] = set()
    for t in transactions:
        if t["flow"] != "debit":
            continue
        blob = f"{t['merchant_clean']} {t['description']}".upper()
        if not _EMI_HINT.search(blob) and t.get("payment_method") != "EMI" and not t.get("is_emi"):
            continue
        key = (t["merchant_clean"], round(t["amount"], 2), t["date"][:7])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "merchant": t["merchant_clean"],
            "amount": round(t["amount"], 2),
            "month": t["date"][:7],
            "confidence": "high" if _EMI_HINT.search(blob) else "medium",
        })
    out.sort(key=lambda x: -x["amount"])
    return out[:20]


def _detect_recurring(transactions: Iterable[NormalizedTransaction]) -> list[dict[str, Any]]:
    """Group by merchant + rounded amount; flag 2+ similar debits across months."""
    buckets: dict[tuple[str, int], list[NormalizedTransaction]] = defaultdict(list)
    for t in transactions:
        if t["flow"] != "debit":
            continue
        if t["amount"] < 10:
            continue
        r = int(round(t["amount"] / 50.0) * 50)
        key = (t["merchant_clean"].lower()[:60], r)
        buckets[key].append(t)

    out: list[dict[str, Any]] = []
    for (merch, rounded), items in buckets.items():
        if len(items) < 2:
            continue
        months = {x["date"][:7] for x in items}
        if len(months) < 2 and len(items) < 3:
            continue
        avg = round(sum(x["amount"] for x in items) / len(items), 2)
        out.append({
            "merchant": items[0]["merchant_clean"],
            "rounded_amount_inr": rounded,
            "occurrences": len(items),
            "months_spanned": len(months),
            "avg_amount": avg,
            "is_subscription": bool(_SUBSCRIPTION_HINT.search(items[0]["merchant_clean"])),
            "is_investment": bool(_INVESTMENT_HINT.search(items[0]["merchant_clean"])),
        })
    out.sort(key=lambda x: (-x["occurrences"], -x["avg_amount"]))
    return out[:25]


def build_summary_facts(engine_out: dict[str, Any]) -> dict[str, Any]:
    """Aggregated non-sensitive facts for Gemini narrative — no raw transactions."""
    k = engine_out["kpis"]
    return {
        "kpis": {
            "total_income": k["total_income"],
            "total_expenses": k["total_expenses"],
            "net_savings": k["net_savings"],
            "savings_rate_pct": k["savings_rate_pct"],
            "investment_total": k["investment_total"],
            "investment_rate_pct": k["investment_rate_pct"],
            "emi_total": k["emi_total"],
            "cash_reliance_pct": k["cash_reliance_pct"],
            "fixed_ratio_pct": k["fixed_ratio_pct"],
        },
        "top_spending_categories": engine_out["charts"]["category_breakdown"][:5],
        "emi_count": len(engine_out.get("emi_candidates", [])),
        "recurring_patterns_count": len(engine_out.get("recurring", [])),
        "period_months": engine_out["charts"]["monthly_flow"]["labels"],
        "profile": engine_out.get("profile") or {},
        "income_profile": engine_out.get("income_profile") or {},
        "stress_indicators": engine_out.get("stress_indicators") or {},
        "behavioral_insights": engine_out.get("behavioral_insights") or {},
    }


def transaction_date_span(transactions: list[NormalizedTransaction]) -> tuple[str | None, str | None]:
    if not transactions:
        return None, None
    dates = [t["date"] for t in transactions]
    return min(dates), max(dates)
