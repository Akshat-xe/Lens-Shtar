from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from app.analysis.models import NormalizedTransaction

_SUBSCRIPTION = re.compile(
    r"netflix|spotify|prime|youtube|apple|google\s*one|dropbox|notion|audible|hotstar|sony\s*liv|zee5",
    re.I,
)


def detect_money_leaks(
    transactions: list[NormalizedTransaction],
    _recurring: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    leaks: list[dict[str, Any]] = []
    debit_counts = Counter()
    for t in transactions:
        if t["flow"] == "debit":
            debit_counts[t["merchant_clean"].lower()[:80]] += 1

    # Duplicate subscription-like merchants same month
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
            leaks.append(
                {
                    "type": "duplicate_subscription",
                    "severity": "high" if len(items) > 2 else "medium",
                    "title": f"Multiple charges for {m0}",
                    "detail": f"{len(items)} similar debits in {month} totaling ₹{total:,.0f}. Check duplicate app store or platform logins.",
                    "estimated_monthly_impact_inr": round(total, 2),
                }
            )

    # Repeated small transactions (impulse / micro-spend)
    small_buckets: dict[str, list[NormalizedTransaction]] = defaultdict(list)
    for t in transactions:
        if t["flow"] != "debit":
            continue
        if t["amount"] > 500:
            continue
        small_buckets[t["merchant_clean"].lower()[:80]].append(t)

    for merch, items in small_buckets.items():
        if len(items) < 5:
            continue
        total = round(sum(i["amount"] for i in items), 2)
        leaks.append(
            {
                "type": "repeated_small_transactions",
                "severity": "medium",
                "title": f"Frequent small spends at {items[0]['merchant_clean']}",
                "detail": f"{len(items)} transactions under ₹500 — pattern suggests impulse or micro-habit spending (total ₹{total:,.0f}).",
                "estimated_monthly_impact_inr": total,
            }
        )

    # Single charge for a subscription-like merchant in-window (audit trail)
    seen_unused: set[str] = set()
    for t in transactions:
        if t["flow"] != "debit":
            continue
        k = t["merchant_clean"].lower()[:80]
        if not _SUBSCRIPTION.search(t["merchant_clean"]) and not _SUBSCRIPTION.search(t["description"]):
            continue
        if debit_counts.get(k, 0) != 1:
            continue
        if k in seen_unused:
            continue
        seen_unused.add(k)
        leaks.append(
            {
                "type": "unused_service",
                "severity": "low",
                "title": f"Review subscription: {t['merchant_clean']}",
                "detail": "Only one debit in this export — confirm renewals/off-cycle billing or cancel if unused.",
                "estimated_monthly_impact_inr": round(t["amount"], 2),
            }
        )

    # Dedup leaks by title
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
