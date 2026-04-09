from __future__ import annotations

from typing import Any, Literal, TypedDict


class NormalizedTransaction(TypedDict, total=False):
    date: str                          # ISO YYYY-MM-DD
    amount: float                      # positive magnitude
    flow: Literal["credit", "debit"]
    merchant_raw: str
    merchant_clean: str
    category: str
    sub_category: str
    description: str
    payment_method: str
    is_emi: bool
    is_recurring: bool
    is_investment: bool
    is_insurance: bool
    stress_flag: bool


DashboardTx = dict[str, Any]
