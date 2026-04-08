from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from app.analysis.models import NormalizedTransaction

_EMI_HINT = re.compile(
    r"\bemi\b|loan\b|nach\b|ach\b|auto\s*debit|si\s|standing\s*instr|ecs\b|mortgage|finance",
    re.I,
)
_SUBSCRIPTION_HINT = re.compile(
    r"netflix|spotify|youtube\s*premium|prime\s*video|apple\.com|google\s*one|dropbox|notion|cursor|github|openai|chatgpt",
    re.I,
)


def _month_key(iso_date: str) -> str:
    return iso_date[:7]


def run_financial_engine(transactions: list[NormalizedTransaction]) -> dict[str, Any]:
    income = 0.0
    expenses = 0.0
    upi_spend = 0.0
    category_debit_totals: dict[str, float] = defaultdict(float)
    monthly_income: dict[str, float] = defaultdict(float)
    monthly_expense: dict[str, float] = defaultdict(float)

    for t in transactions:
        amt = float(t["amount"])
        if t["flow"] == "credit":
            income += amt
            monthly_income[_month_key(t["date"])] += amt
        else:
            expenses += amt
            monthly_expense[_month_key(t["date"])] += amt
            cat = t["category"]
            category_debit_totals[cat] += amt
            if "upi" in (t.get("payment_method") or "").lower():
                upi_spend += amt
            blob = f"{t['merchant_clean']} {t['description']}".lower()
            if "upi" in blob and t.get("payment_method") == "Other":
                upi_spend += amt

    savings = income - expenses
    savings_rate_pct = round((savings / income * 100.0), 1) if income > 0 else 0.0

    debit_total = sum(category_debit_totals.values()) or 1.0
    category_breakdown = [
        {"category": k, "amount": round(v, 2), "pct": round(v / debit_total * 100.0, 1)}
        for k, v in sorted(category_debit_totals.items(), key=lambda x: -x[1])
    ]

    months_sorted = sorted(set(monthly_income.keys()) | set(monthly_expense.keys()))
    monthly_flow = {
        "labels": months_sorted,
        "income": [round(monthly_income[m], 2) for m in months_sorted],
        "expenses": [round(monthly_expense[m], 2) for m in months_sorted],
    }

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
            "description": t["description"],
            "payment_method": t["payment_method"],
        }
        for t in sorted(transactions, key=lambda x: x["date"], reverse=True)
    ]

    kpis = {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "savings": round(savings, 2),
        "savings_rate_pct": savings_rate_pct,
        "upi_spend": round(upi_spend, 2),
        "emi_monthly_estimate": emi_monthly_estimate,
        "transaction_count": len(transactions),
    }

    charts = {
        "category_breakdown": category_breakdown[:12],
        "monthly_flow": monthly_flow,
    }

    return {
        "kpis": kpis,
        "charts": charts,
        "emi_candidates": emi_candidates,
        "recurring": recurring,
        "transactions": tx_out,
    }


def _detect_emi_candidates(transactions: Iterable[NormalizedTransaction]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, float, str]] = set()
    for t in transactions:
        if t["flow"] != "debit":
            continue
        blob = f"{t['merchant_clean']} {t['description']}".upper()
        if not _EMI_HINT.search(blob) and t.get("payment_method") != "EMI":
            continue
        key = (t["merchant_clean"], round(t["amount"], 2), t["date"][:7])
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "merchant": t["merchant_clean"],
                "amount": round(t["amount"], 2),
                "month": t["date"][:7],
                "confidence": "high" if _EMI_HINT.search(blob) else "medium",
            }
        )
    out.sort(key=lambda x: -x["amount"])
    return out[:20]


def _detect_recurring(transactions: Iterable[NormalizedTransaction]) -> list[dict[str, Any]]:
    """Group by merchant + rounded amount; flag 3+ similar debits."""
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
        if len(items) < 3:
            continue
        avg = round(sum(x["amount"] for x in items) / len(items), 2)
        months = {x["date"][:7] for x in items}
        out.append(
            {
                "merchant": items[0]["merchant_clean"],
                "rounded_amount_inr": rounded,
                "occurrences": len(items),
                "months_spanned": len(months),
                "avg_amount": avg,
                "likely_subscription": bool(_SUBSCRIPTION_HINT.search(items[0]["merchant_clean"])),
            }
        )
    out.sort(key=lambda x: (-x["occurrences"], -x["avg_amount"]))
    return out[:25]


def build_summary_facts(engine_out: dict[str, Any]) -> dict[str, Any]:
    """Non-sensitive aggregates only — safe to send to Gemini for narrative."""
    k = engine_out["kpis"]
    top_cat = engine_out["charts"]["category_breakdown"][:5]
    return {
        "kpis": k,
        "top_spending_categories": top_cat,
        "emi_count": len(engine_out.get("emi_candidates", [])),
        "recurring_patterns_count": len(engine_out.get("recurring", [])),
        "period_months": engine_out["charts"]["monthly_flow"]["labels"],
    }


def transaction_date_span(transactions: list[NormalizedTransaction]) -> tuple[str | None, str | None]:
    if not transactions:
        return None, None
    dates = [t["date"] for t in transactions]
    return min(dates), max(dates)
