from __future__ import annotations

from typing import Any

from app.analysis.models import NormalizedTransaction


def build_savings_suggestions(
    kpis: dict[str, Any],
    category_breakdown: list[dict[str, Any]],
    leaks: list[dict[str, Any]],
    upi_spend: float,
) -> dict[str, list[dict[str, Any]]]:
    quick_wins: list[dict[str, Any]] = []
    monthly: list[dict[str, Any]] = []
    long_term: list[dict[str, Any]] = []

    # Quick wins from high-severity leaks
    for L in leaks:
        if L["severity"] == "high" and L["type"] == "duplicate_subscription":
            quick_wins.append(
                {
                    "title": "Remove duplicate subscription charges",
                    "detail": L["detail"],
                    "impact_inr_month_estimate": L.get("estimated_monthly_impact_inr"),
                    "bucket": "Quick Wins",
                }
            )
            break

    food_pct = next((c["pct"] for c in category_breakdown if "food" in c["category"].lower()), None)
    if food_pct and food_pct > 18:
        monthly.append(
            {
                "title": "Cap food delivery / dining",
                "detail": f"Food & dining is {food_pct}% of spend — try a weekly ₹ cap or batch grocery runs.",
                "impact_inr_month_estimate": round(kpis.get("expenses", 0) * 0.05, 2),
                "bucket": "Monthly Optimization",
            }
        )

    if upi_spend > 0 and kpis.get("expenses", 0) > 0:
        ratio = upi_spend / kpis["expenses"]
        if ratio > 0.35:
            monthly.append(
                {
                    "title": "Audit high UPI velocity",
                    "detail": f"UPI is ~{ratio*100:.0f}% of expenses — many small UPI debits add stealth drag.",
                    "impact_inr_month_estimate": round(upi_spend * 0.08, 2),
                    "bucket": "Monthly Optimization",
                }
            )

    subs = [c for c in category_breakdown if "subscription" in c["category"].lower()]
    if subs:
        monthly.append(
            {
                "title": "Subscription consolidation pass",
                "detail": "List all active subscriptions; cancel overlaps and annualize where cheaper.",
                "impact_inr_month_estimate": round(subs[0]["amount"] * 0.25, 2),
                "bucket": "Monthly Optimization",
            }
        )

    if kpis.get("savings_rate_pct", 0) < 15 and kpis.get("income", 0) > 0:
        long_term.append(
            {
                "title": "Automate a minimum savings rule",
                "detail": "Route a fixed % of inflow to a separate account on salary day before discretionary spend.",
                "impact_inr_month_estimate": round(kpis["income"] * 0.1, 2),
                "bucket": "Long-Term",
            }
        )

    if kpis.get("emi_monthly_estimate", 0) > kpis.get("income", 1) * 0.35:
        long_term.append(
            {
                "title": "EMI load is elevated vs income",
                "detail": "Consider restructuring high-cost debt or accelerating payoff on the highest APR line first.",
                "impact_inr_month_estimate": None,
                "bucket": "Long-Term",
            }
        )

    # Trim lists
    return {
        "quick_wins": quick_wins[:5],
        "monthly_optimization": monthly[:7],
        "long_term": long_term[:5],
    }


def rule_based_fallback_summary(transactions: list[NormalizedTransaction], kpis: dict[str, Any]) -> str:
    return (
        f"Income ₹{kpis.get('income', 0):,.0f} vs expenses ₹{kpis.get('expenses', 0):,.0f}. "
        f"Savings ₹{kpis.get('savings', 0):,.0f} (rate {kpis.get('savings_rate_pct', 0):.1f}%). "
        f"Focus categories: review subscriptions and UPI micro-transactions if savings rate is below your goal."
    )
