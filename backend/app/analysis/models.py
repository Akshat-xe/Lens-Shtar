from __future__ import annotations

from typing import Any, Literal, TypedDict


class TransactionDict(TypedDict, total=False):
    date: str  # ISO YYYY-MM-DD
    amount: float  # positive magnitude
    flow: Literal["credit", "debit"]
    merchant_raw: str
    merchant_clean: str
    category: str
    description: str
    payment_method: str


class NormalizedTransaction(TypedDict):
    date: str
    amount: float
    flow: Literal["credit", "debit"]
    merchant_raw: str
    merchant_clean: str
    category: str
    description: str
    payment_method: str


DashboardTx = dict[str, Any]
