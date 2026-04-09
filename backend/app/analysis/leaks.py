from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from app.analysis.models import NormalizedTransaction

import statistics

_SUBSCRIPTION = re.compile(
    r"netflix|spotify|prime|youtube|apple|google\s*one|dropbox|notion|audible|hotstar|sony\s*liv|zee5|jio"
    r"|mxplayer|disney|paramount|cursor|openai|chatgpt|github|notion",
    re.I,
)
_INVESTMENT = re.compile(r"\bsip\b|mutual\s*fund|nps\b|ppf\b|elss\b|zerodha|groww|kuvera|\brd\b|\bfd\b", re.I)


def compute_behavioral_analytics(transactions: list[NormalizedTransaction], income: float, expenses: float) -> dict[str, Any]:
    from datetime import datetime
    
    weekend_spend = 0.0
    weekday_spend = 0.0
    month_end_balance_dips = 0

    prev_balance = None
    for t in transactions:
        if t["flow"] == "debit":
            try:
                dt = datetime.strptime(t["date"], "%Y-%m-%d")
                if dt.weekday() >= 5:  # Saturday or Sunday
                    weekend_spend += t["amount"]
                else:
                    weekday_spend += t["amount"]
                
                # Check month end stress (days 25-31)
                if dt.day >= 25 and t.get("balance_after") is not None:
                    if float(t["balance_after"]) < (income * 0.10): # below 10% of monthly income means extreme cash crunch
                        month_end_balance_dips += 1
            except Exception:
                pass

    weekend_ratio = (weekend_spend / expenses) if expenses > 0 else 0.0

    return {
        "weekend_spend_pct": round(weekend_ratio * 100, 1),
        "month_end_stress_events": month_end_balance_dips,
        "is_impulsive_weekend_shopper": weekend_ratio > 0.40,
    }


def detect_money_leaks(
    transactions: list[NormalizedTransaction],
    _recurring: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    leaks: list[dict[str, Any]] = []
    debit_counts: Counter = Counter()
    for t in transactions:
        if t["flow"] == "debit":
            debit_counts[t["merchant_clean"].lower()[:80]] += 1

    # ── 1. Duplicate subscription charges same month ──────────────────────────
    by_month_merch: dict[tuple[str, str], list[NormalizedTransaction]] = defaultdict(list)
    for t in transactions:
        if t["flow"] != "debit":
            continue
        key = (t["date"][:7], t["merchant_clean"].lower()[:80])
        by_month_merch[key].append(t)

    for (month, merch_key), items in by_month_merch.items():
        if len(items) < 2:
            continue
        m0 = items[0]["merchant_clean"]
        if _SUBSCRIPTION.search(m0) or any(_SUBSCRIPTION.search(i["merchant_clean"]) for i in items):
            total = round(sum(i["amount"] for i in items), 2)
            leaks.append({
                "type": "duplicate_subscription",
                "severity": "high",
                "title": f"Duplicate charge: {m0}",
                "detail": f"{len(items)} debits in {month} totaling ₹{total:,.0f} — check for double billing or multiple plan logins.",
                "estimated_monthly_impact_inr": round(total, 2),
            })

    # ── 2. Repeated small impulse spends ─────────────────────────────────────
    small_buckets: dict[str, list[NormalizedTransaction]] = defaultdict(list)
    for t in transactions:
        if t["flow"] != "debit" or t["amount"] > 600:
            continue
        small_buckets[t["merchant_clean"].lower()[:80]].append(t)

    for merch, items in small_buckets.items():
        if len(items) < 5:
            continue
        total = round(sum(i["amount"] for i in items), 2)
        leaks.append({
            "type": "repeated_small_spend",
            "severity": "medium",
            "title": f"Micro-habit spend: {items[0]['merchant_clean']}",
            "detail": f"{len(items)} transactions under ₹600 totaling ₹{total:,.0f} — impulse pattern detected.",
            "estimated_monthly_impact_inr": total,
        })

    # ── 3. Unused or single-occurrence subscription ───────────────────────────
    seen_unused: set[str] = set()
    for t in transactions:
        if t["flow"] != "debit":
            continue
        k = t["merchant_clean"].lower()[:80]
        if not _SUBSCRIPTION.search(t["merchant_clean"]) and not _SUBSCRIPTION.search(t.get("description") or ""):
            continue
        if debit_counts.get(k, 0) != 1:
            continue
        if k in seen_unused:
            continue
        seen_unused.add(k)
        leaks.append({
            "type": "unused_subscription",
            "severity": "low",
            "title": f"Review subscription: {t['merchant_clean']}",
            "detail": f"Only 1 charge visible — confirm whether you actively use this or cancel if idle. ₹{t['amount']:,.0f}/period.",
            "estimated_monthly_impact_inr": round(t["amount"], 2),
        })

    # ── 4. High cash ATM reliance ─────────────────────────────────────────────
    atm_txs = [t for t in transactions if t["flow"] == "debit" and t["payment_method"] == "Cash"]
    if atm_txs:
        atm_total = sum(t["amount"] for t in atm_txs)
        total_debits = sum(t["amount"] for t in transactions if t["flow"] == "debit") or 1
        if atm_total / total_debits > 0.20:
            leaks.append({
                "type": "high_cash_reliance",
                "severity": "medium",
                "title": "High cash/ATM withdrawal pattern",
                "detail": f"₹{atm_total:,.0f} withdrawn as cash ({atm_total/total_debits*100:.0f}% of expenses) — cash spending is invisible and untrackable.",
                "estimated_monthly_impact_inr": round(atm_total, 2),
            })

    # ── 5. EMI burden > 40% of income ────────────────────────────────────────
    emi_txs = [t for t in transactions if t["flow"] == "debit" and t.get("is_emi")]
    income_txs = [t for t in transactions if t["flow"] == "credit"]
    if emi_txs and income_txs:
        emi_total = sum(t["amount"] for t in emi_txs)
        income_total = sum(t["amount"] for t in income_txs) or 1
        if emi_total / income_total > 0.40:
            leaks.append({
                "type": "emi_overload",
                "severity": "high",
                "title": "EMI burden exceeds 40% of income",
                "detail": f"Total EMIs ₹{emi_total:,.0f} = {emi_total/income_total*100:.0f}% of income. This is above the healthy 35% threshold — risk of cash crunch.",
                "estimated_monthly_impact_inr": round(emi_total, 2),
            })

    # ── 6. Stress flags (overdraft, penalties) ────────────────────────────────
    stress_txs = [t for t in transactions if t.get("stress_flag")]
    if stress_txs:
        total_stress = sum(t["amount"] for t in stress_txs)
        leaks.append({
            "type": "stress_charges",
            "severity": "high",
            "title": f"Financial stress charges detected ({len(stress_txs)} events)",
            "detail": f"Overdraft fees, bounce charges, or penalties totaling ₹{total_stress:,.0f} — address underlying cash-flow timing issues.",
            "estimated_monthly_impact_inr": round(total_stress, 2),
        })

    # ── 7. Statistical Outliers (Amount > Mean + 3 StdDev) ───────────────────
    debits = [t["amount"] for t in transactions if t["flow"] == "debit" and t["amount"] > 0]
    if len(debits) >= 10:
        mean_spd = statistics.mean(debits)
        std_spd = statistics.stdev(debits) if len(debits) > 1 else 0
        threshold = mean_spd + (3 * std_spd)
        
        # Only flag if threshold is meaningful (e.g. at least 5000)
        if threshold > 5000:
            outliers = [t for t in transactions if t["flow"] == "debit" and t["amount"] > threshold and not t.get("is_investment") and not t.get("is_emi")]
            for o in outliers:
                leaks.append({
                    "type": "statistical_outlier",
                    "severity": "medium",
                    "title": f"Unusually large expense: {o['merchant_clean']}",
                    "detail": f"₹{o['amount']:,.0f} is a severe statistical outlier (average spend is ₹{mean_spd:,.0f}). Normal? Or irregular spike?",
                    "estimated_monthly_impact_inr": None,
                })

    # ── 8. Rapid-Fire Double Charges ─────────────────────────────────────────
    by_date_merch: dict[tuple[str, str], list[NormalizedTransaction]] = defaultdict(list)
    for t in transactions:
        if t["flow"] == "debit":
            key = (t["date"], t["merchant_clean"].lower()[:80])
            by_date_merch[key].append(t)
            
    for (dt, merch), items in by_date_merch.items():
        if len(items) >= 2:
            amounts = [i["amount"] for i in items]
            if amounts.count(amounts[0]) >= 2: # Exact same amount charged multiple times same day
                amt = amounts[0]
                leaks.append({
                    "type": "rapid_fire_charge",
                    "severity": "high", # high severity since duplicate deductions are common bank/merchant glitches
                    "title": f"Potential Double Charge: {items[0]['merchant_clean']}",
                    "detail": f"Charged ₹{amt:,.0f} {amounts.count(amt)} times on {dt}. Verify if this was intentional or a payment gateway glitch.",
                    "estimated_monthly_impact_inr": round(amt * (amounts.count(amt) - 1), 2),
                })

    # ── 9. Mass Exodus Transfers (>50% of monthly debit volume) ──────────────
    total_debit_vol = sum(debits)
    if total_debit_vol > 0:
        for t in transactions:
            if t["flow"] == "debit" and t["amount"] >= (total_debit_vol * 0.5):
                # Ensure it's not an internal recognized investment
                if not t.get("is_investment"):
                    leaks.append({
                        "type": "mass_exodus_transfer",
                        "severity": "high",
                        "title": "Massive single-day outflow",
                        "detail": f"₹{t['amount']:,.0f} to {t['merchant_clean']} consumed {((t['amount']/total_debit_vol)*100):.0f}% of total outbound volume. Ensure account security.",
                        "estimated_monthly_impact_inr": None,
                    })

    # ── Dedup & sort ──────────────────────────────────────────────────────────
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for L in leaks:
        key = L["title"][:120]
        if key in seen:
            continue
        seen.add(key)
        unique.append(L)
    unique.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]])
    return unique[:30]
