from __future__ import annotations

from typing import Any

from app.analysis.models import NormalizedTransaction


def build_savings_suggestions(
    kpis: dict[str, Any],
    category_breakdown: list[dict[str, Any]],
    leaks: list[dict[str, Any]],
    upi_spend: float,
    behavioral_insights: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    bi = behavioral_insights or {}
    quick_wins: list[dict[str, Any]] = []
    monthly: list[dict[str, Any]] = []
    long_term: list[dict[str, Any]] = []

    income = kpis.get("total_income") or kpis.get("income", 0)
    expenses = kpis.get("total_expenses") or kpis.get("expenses", 0)
    savings_rate = kpis.get("savings_rate_pct", 0)
    emi_total = kpis.get("emi_total", 0)
    investment_total = kpis.get("investment_total", 0)
    cash_pct = kpis.get("cash_reliance_pct", 0)
    fixed_ratio = kpis.get("fixed_ratio_pct", 0)

    cat_map = {c["category"].lower(): c for c in category_breakdown}

    # ── Quick Wins ─────────────────────────────────────────────────────────────
    for leak in leaks:
        if leak["severity"] == "high":
            if leak["type"] == "duplicate_subscription":
                quick_wins.append({
                    "title": "🔁 Remove duplicate subscription",
                    "detail": leak["detail"],
                    "impact_inr_month_estimate": leak.get("estimated_monthly_impact_inr"),
                    "bucket": "Quick Wins",
                })
                break

    if cash_pct > 20:
        quick_wins.append({
            "title": "📱 Shift cash spending to UPI/Card",
            "detail": f"You rely on cash for {cash_pct:.0f}% of expenses — untracked spending makes budgeting hard. Switch to UPI for visibility.",
            "impact_inr_month_estimate": round(kpis.get("atm_spend", 0) * 0.3, 2),
            "bucket": "Quick Wins",
        })

    if bi.get("post_payday_splurge"):
        quick_wins.append({
            "title": "🎯 Apply 48-hour rule post payday",
            "detail": "Pattern detected: surge in spending within 7 days of salary credit. Park a fixed amount in savings immediately on payday before discretionary spend.",
            "impact_inr_month_estimate": round(income * 0.08, 2) if income else None,
            "bucket": "Quick Wins",
        })

    # ── Monthly Optimization ──────────────────────────────────────────────────
    food_cat = cat_map.get("food & dining") or cat_map.get("food & dining")
    if food_cat and food_cat.get("pct", 0) > 18:
        monthly.append({
            "title": "🍽️ Set food delivery weekly budget",
            "detail": f"Food & Dining is {food_cat['pct']:.0f}% of expenses (₹{food_cat['amount']:,.0f}). Cap at ₹{food_cat['amount']*0.75:,.0f}/mo — batch cook 2 days/week.",
            "impact_inr_month_estimate": round(food_cat["amount"] * 0.25, 2),
            "bucket": "Monthly Optimization",
        })

    if upi_spend > 0 and expenses > 0:
        ratio = upi_spend / expenses
        if ratio > 0.35:
            monthly.append({
                "title": "💸 Audit UPI micro-transactions",
                "detail": f"UPI accounts for {ratio*100:.0f}% of expenses (₹{upi_spend:,.0f}). Many small UPI debits create stealth cash drag — review weekly.",
                "impact_inr_month_estimate": round(upi_spend * 0.10, 2),
                "bucket": "Monthly Optimization",
            })

    subs_cat = cat_map.get("subscriptions")
    if subs_cat and subs_cat.get("amount", 0) > 500:
        monthly.append({
            "title": "📺 Subscription audit pass",
            "detail": f"₹{subs_cat['amount']:,.0f}/mo on subscriptions. List all active ones — cancel overlaps, switch to annual plans where ≥20% cheaper.",
            "impact_inr_month_estimate": round(subs_cat["amount"] * 0.30, 2),
            "bucket": "Monthly Optimization",
        })

    shop_cat = cat_map.get("shopping")
    if shop_cat and shop_cat.get("pct", 0) > 20:
        monthly.append({
            "title": "🛒 Introduce a shopping cool-off rule",
            "detail": f"Shopping is {shop_cat['pct']:.0f}% of spend (₹{shop_cat['amount']:,.0f}). Add items to cart for 24h before purchasing — reduces impulse buys by ~30%.",
            "impact_inr_month_estimate": round(shop_cat["amount"] * 0.20, 2),
            "bucket": "Monthly Optimization",
        })

    # ── Long-Term ─────────────────────────────────────────────────────────────
    if savings_rate < 20 and income > 0:
        target_saving = round(income * 0.20, 2)
        long_term.append({
            "title": "🏦 Automate 20% savings before spending",
            "detail": f"Current savings rate is {savings_rate:.1f}%. Target: 20% = ₹{target_saving:,.0f}/mo. Set auto-transfer on salary day to a separate savings/investment account.",
            "impact_inr_month_estimate": target_saving,
            "bucket": "Long-Term",
        })

    if investment_total == 0 and income > 0:
        long_term.append({
            "title": "📈 Start a SIP (Systematic Investment Plan)",
            "detail": "No investment transactions detected. Starting a ₹500–5000/mo index fund SIP builds long-term wealth through compounding — even small amounts matter.",
            "impact_inr_month_estimate": round(income * 0.05, 2),
            "bucket": "Long-Term",
        })
    elif investment_total > 0 and income > 0 and investment_total / income < 0.10:
        inv_gap = round(income * 0.10 - investment_total, 2)
        long_term.append({
            "title": "📈 Increase investment rate to 10% of income",
            "detail": f"Current investment rate {investment_total/income*100:.1f}% — target 10% (₹{income*0.10:,.0f}/mo). Top up existing SIPs or add new instruments.",
            "impact_inr_month_estimate": inv_gap if inv_gap > 0 else None,
            "bucket": "Long-Term",
        })

    if emi_total > income * 0.35 and income > 0:
        long_term.append({
            "title": "⚠️ Reduce EMI obligation (debt restructuring)",
            "detail": f"EMIs = {emi_total/income*100:.0f}% of income (₹{emi_total:,.0f}). Target <35%. Consider paying down the highest APR loan first or negotiating restructuring.",
            "impact_inr_month_estimate": None,
            "bucket": "Long-Term",
        })

    if fixed_ratio > 65:
        long_term.append({
            "title": "📊 Reduce fixed obligation ratio",
            "detail": f"Fixed expenses are {fixed_ratio:.0f}% of your spending. High fixed ratios leave no buffer — look to renegotiate rent, consolidate debt, or pause non-essential subscriptions.",
            "impact_inr_month_estimate": None,
            "bucket": "Long-Term",
        })

    return {
        "quick_wins": quick_wins[:5],
        "monthly_optimization": monthly[:7],
        "long_term": long_term[:5],
    }


def rule_based_fallback_summary(transactions: list[NormalizedTransaction], kpis: dict[str, Any]) -> str:
    income = kpis.get("total_income") or kpis.get("income", 0)
    expenses = kpis.get("total_expenses") or kpis.get("expenses", 0)
    savings = kpis.get("net_savings") or kpis.get("savings", 0)
    rate = kpis.get("savings_rate_pct", 0)
    inv = kpis.get("investment_total", 0)
    emi = kpis.get("emi_total", 0)
    cash_pct = kpis.get("cash_reliance_pct", 0)

    health = "healthy" if rate >= 20 else ("moderate" if rate >= 10 else "needs attention")
    inv_note = f" Investment activity: ₹{inv:,.0f}." if inv > 0 else " No investment activity detected — consider starting a SIP."
    emi_note = f" EMI commitments: ₹{emi:,.0f}/mo." if emi > 0 else ""
    cash_note = f" Cash reliance at {cash_pct:.0f}% — shift to digital for tracking." if cash_pct > 20 else ""

    return (
        f"Total income ₹{income:,.0f} vs expenses ₹{expenses:,.0f} — "
        f"net savings ₹{savings:,.0f} (savings rate {rate:.1f}%: {health})."
        f"{inv_note}{emi_note}{cash_note} "
        f"Review top spending categories and set category-wise monthly limits for better control."
    )
